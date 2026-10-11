"""Grounding, correct human interactions and true image-edit inputs."""
import io
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from PIL import Image, ImageDraw
from google.genai import types
import creative_pipeline as creative


@pytest.mark.parametrize("product,interaction,words", [
    ({"name": "Pocky chocolate", "category": "Dulces"}, "eat", "tasting/eating"),
    ({"name": "Palillos", "category": "Cocina y Accesorios"}, "use", "correctly using"),
    ({"name": "Ramune", "category": "Bebidas"}, "drink", "drinking"),
    ({"name": "Salsa de soja", "category": "Abarrotes"}, "prepare", "preparing"),
])
def test_no_ad_fallback_requires_real_human_interaction(product, interaction, words):
    plan = creative.fallback_brief(product)
    assert plan["interaction"] == interaction
    assert "adult" in plan["lifestyle"].lower()
    assert words in plan["lifestyle"]
    assert plan["ads_found"] is False and plan["sources"] == []
    assert "artistic" in plan["comercial"]


def test_grounded_research_does_not_accept_invented_sources():
    plan = {"lifestyle": "A motionless plain product still life with no person.",
            "comercial": "Expressive painted red and purple artistic world around the product.",
            "ads_found": True, "note": "Un anuncio", "sources": [{"url": "https://invented.example"}]}
    response = NS(text="```json\n"+json.dumps(plan)+"\n```", candidates=[])
    client = NS(models=NS(generate_content=Mock(return_value=response)))
    result = creative.brief(client, {"name": "Pocky", "category": "Dulces"})
    assert result["sources"] == [] and result["ads_found"] is False
    assert "adult" in result["lifestyle"].lower()
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.tools[0].google_search is not None
    assert config.response_mime_type is None  # Compatible with grounded Gemini 2.5.
    assert config.thinking_config.thinking_budget == 0


def test_real_grounding_and_search_suggestions_are_preserved():
    plan = {"lifestyle": "An adult eating this snack outdoors with its package in view.",
            "comercial": "An artistic advertising scene with expressive color and motion.",
            "ads_found": True, "note": "Inspiración de una campaña verificada"}
    meta = NS(grounding_chunks=[NS(web=NS(uri="https://brand.example/campaign", title="Brand campaign"))],
              search_entry_point=NS(rendered_content="<div>Search suggestions</div>"))
    response = NS(text=json.dumps(plan), candidates=[NS(grounding_metadata=meta)])
    client = NS(models=NS(generate_content=Mock(return_value=response)))
    result = creative.brief(client, {"name": "Snack", "category": "Dulces"})
    assert result["ads_found"] is True
    assert result["sources"][0]["url"] == "https://brand.example/campaign"
    assert result["search_suggestions"] == "<div>Search suggestions</div>"


def test_no_ads_still_uses_gemini_original_human_scene():
    plan = {"lifestyle": "An adult tasting Pocky at a picnic table, holding its exact red package.",
            "comercial": "An artistic advertising scene with expressive color and motion.", "ads_found": False}
    client = NS(models=NS(generate_content=Mock(return_value=NS(text=json.dumps(plan), candidates=[]))))
    result = creative.brief(client, {"name": "Pocky", "category": "Dulces"})
    assert result["lifestyle"] == plan["lifestyle"]
    assert result["ads_found"] is False


def test_edit_uses_original_previous_style_and_all_corrections(tmp_path):
    paths = []
    for index, color in enumerate(("red", "orange", "purple")):
        path = tmp_path / f"reference{index}.png"
        Image.new("RGB", (60,80), color).save(path)
        paths.append(str(path))
    contents = creative.image_contents([paths[0]], "Decorative scene", "3_comercial", previous=paths[1],
        styles=[paths[2]], corrections=["Keep red packaging", "Fix the hands"])
    images = [part for part in contents if isinstance(part, types.Part)]
    assert len(images) == 3
    assert all(part.inline_data.mime_type == "image/jpeg" for part in images)
    text = " ".join(part for part in contents if isinstance(part, str))
    assert "PRODUCT REFERENCE" in text and "PREVIOUS GENERATED IMAGE TO EDIT" in text
    assert "STYLE ONLY" in text and "Keep red packaging" in text and "Fix the hands" in text
    config = creative.image_config()
    assert config.response_modalities == ["TEXT", "IMAGE"]
    assert config.image_config.aspect_ratio == "1:1"


def test_generator_uses_one_native_image_call_and_ignores_thought_images(tmp_path):
    path = tmp_path / "product.jpg"
    image = Image.new("RGB", (1024,1024), "white")
    ImageDraw.Draw(image).rectangle((100,100,900,900), fill="red")
    image.save(path)
    output = io.BytesIO(); image.save(output, "PNG")
    response = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[
        types.Part(thought=True, inline_data=types.Blob(mime_type="image/png", data=b"ignore")),
        types.Part.from_bytes(data=output.getvalue(), mime_type="image/png")]))])
    client = NS(models=NS(generate_content=Mock(return_value=response)))
    result = creative.generate(client, [str(path)], "Adults eating the snack", "2_uso")
    assert result.size == (1024,1024)
    client.models.generate_content.assert_called_once()


def test_empty_provider_result_has_actionable_error_without_retry(tmp_path):
    path = tmp_path / "product.jpg"
    Image.new("RGB", (60,80), "red").save(path)
    client = NS(models=NS(generate_content=Mock(return_value=types.GenerateContentResponse(candidates=[]))))
    with pytest.raises(ValueError, match="no devolvió una imagen"):
        creative.generate(client, [str(path)], "Scene", "1_hd")
    client.models.generate_content.assert_called_once()
