"""Job kinds supported by the local application. Old rows remain historical."""
SUPPORTED_JOB_KINDS = frozenset({"generation", "studio_generation", "asset_save", "import", "enrichment", "woocommerce_export"})
