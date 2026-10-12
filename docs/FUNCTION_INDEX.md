# Índice de funciones actual

Generado de la rama de limpieza. No contiene módulos retirados; la responsabilidad por módulo está en CODE_MAP.md.

## ai_app.py

| Objeto | Tipo | Línea |
|---|---|---|
| [sheets_for_session](../ai_app.py#L13) | función | 13 |
| [_clean](../ai_app.py#L21) | función | 21 |
| [_canonical_row](../ai_app.py#L30) | función | 30 |
| [_read_master](../ai_app.py#L84) | función | 84 |
| [_append_master_row](../ai_app.py#L109) | función | 109 |
| [_no_variable_sync](../ai_app.py#L138) | función | 138 |
| [_no_legacy_format](../ai_app.py#L142) | función | 142 |

## app.py

| Objeto | Tipo | Línea |
|---|---|---|
| [field_update](../app.py#L45) | función | 45 |
| [_env_requerida](../app.py#L63) | función | 63 |
| [_construir_correccion](../app.py#L187) | función | 187 |
| [_nueva_session_id](../app.py#L250) | función | 250 |
| [_eliminar_sesion](../app.py#L255) | función | 255 |
| [_guardar_sesion](../app.py#L268) | función | 268 |
| [_obtener_sesion](../app.py#L293) | función | 293 |
| [_validar_sesion](../app.py#L307) | función | 307 |
| [login](../app.py#L327) | función | 327 |
| [auth_callback](../app.py#L352) | función | 352 |
| [logout](../app.py#L412) | función | 412 |
| [_get_drive_service](../app.py#L424) | función | 424 |
| [_get_sheets_service](../app.py#L439) | función | 439 |
| [_buscar_o_crear_carpeta](../app.py#L451) | función | 451 |
| [_buscar_archivo](../app.py#L466) | función | 466 |
| [_buscar_inventario_importable](../app.py#L475) | función | 475 |
| [_convertir_inventario_importable](../app.py#L501) | función | 501 |
| [_validar_inventario_preparado](../app.py#L530) | función | 530 |
| [_obtener_gid_inventario](../app.py#L552) | función | 552 |
| [_aplicar_formato_base](../app.py#L587) | función | 587 |
| [_aplicar_formato_filas](../app.py#L695) | función | 695 |
| [_limpiar_valor_sheet](../app.py#L784) | función | 784 |
| [_fila_formato_gabo](../app.py#L798) | función | 798 |
| [_obtener_o_crear_gid_lista_variable](../app.py#L821) | función | 821 |
| [_variante_desde_nombre](../app.py#L859) | función | 859 |
| [_normalizar_fila_variable](../app.py#L876) | función | 876 |
| [_fila_variable_desde_gabo](../app.py#L882) | función | 882 |
| [_aplicar_formato_lista_variable](../app.py#L902) | función | 902 |
| [_sincronizar_lista_variable](../app.py#L993) | función | 993 |
| [_crear_o_encontrar_inventario](../app.py#L1096) | función | 1096 |
| [_leer_csv_legacy](../app.py#L1130) | función | 1130 |
| [_migrar_csv_legacy](../app.py#L1146) | función | 1146 |
| [_preparar_estructura](../app.py#L1165) | función | 1165 |
| [_extraer_folder_id](../app.py#L1218) | función | 1218 |
| [_leer_google_sheet](../app.py#L1233) | función | 1233 |
| [_agregar_fila_google_sheet](../app.py#L1251) | función | 1251 |
| [_cargar_df](../app.py#L1279) | función | 1279 |
| [_subir_imagen_drive](../app.py#L1286) | función | 1286 |
| [_cargar_logo_marca](../app.py#L1308) | función | 1308 |
| [limpiar_texto_sku](../app.py#L1329) | función | 1329 |
| [generar_sku_logica](../app.py#L1338) | función | 1338 |
| [comprimir_imagen](../app.py#L1351) | función | 1351 |
| [estampar_logo](../app.py#L1358) | función | 1358 |
| [_extraer_json](../app.py#L1368) | función | 1368 |
| [_extraer_imagen_bytes](../app.py#L1376) | función | 1376 |
| [_imagen_para_ia](../app.py#L1391) | función | 1391 |
| [estimar_precio_producto](../app.py#L1399) | función | 1399 |
| [_obtener_vocabulario_etiquetas](../app.py#L1426) | función | 1426 |
| [_vocabulario_relevante](../app.py#L1440) | función | 1440 |
| [estimar_etiquetas_producto](../app.py#L1445) | función | 1445 |
| [recalcular_etiquetas_ui](../app.py#L1487) | función | 1487 |
| [buscar_variantes_por_imagen](../app.py#L1497) | función | 1497 |
| [investigar_prompts](../app.py#L1571) | función | 1571 |
| [_rutas_referencia](../app.py#L1580) | función | 1580 |
| [_configuracion_imagen_cuadrada](../app.py#L1587) | función | 1587 |
| [_contrato_visual](../app.py#L1598) | función | 1598 |
| [_validacion_local_imagen](../app.py#L1608) | función | 1608 |
| [_validar_con_vision](../app.py#L1628) | función | 1628 |
| [generar_foto_individual](../app.py#L1671) | función | 1671 |
| [modulo_extraer_textos](../app.py#L1773) | función | 1773 |
| [_rehacer_generico](../app.py#L1876) | función | 1876 |
| [rehacer_hd](../app.py#L1918) | función | 1918 |
| [rehacer_life](../app.py#L1927) | función | 1927 |
| [rehacer_comercial](../app.py#L1937) | función | 1937 |
| [modulo_generar_todo](../app.py#L1947) | función | 1947 |
| [guardar_producto_sheet](../app.py#L1976) | función | 1976 |
| [detectar_padre](../app.py#L2026) | función | 2026 |
| [cambio_tipo_ui](../app.py#L2067) | función | 2067 |
| [aplicar_recomendacion_tipo](../app.py#L2074) | función | 2074 |
| [recalcular_sku_ui](../app.py#L2084) | función | 2084 |
| [recalcular_precio_ui](../app.py#L2088) | función | 2088 |
| [obtener_categorias](../app.py#L2096) | función | 2096 |
| [obtener_subcategorias](../app.py#L2108) | función | 2108 |
| [_estado_login_html](../app.py#L2123) | función | 2123 |
| [cargar_estado_inicial](../app.py#L2149) | función | 2149 |
| [guardar_api_key](../app.py#L2164) | función | 2164 |
| [refrescar_categorias](../app.py#L2187) | función | 2187 |
| [guardar_carpeta_personalizada](../app.py#L2191) | función | 2191 |
| [limpiar_feedback](../app.py#L2260) | función | 2260 |

## app_security.py

| Objeto | Tipo | Línea |
|---|---|---|
| [clean_html](../app_security.py#L21) | función | 21 |
| [validate_service_url](../app_security.py#L27) | función | 27 |
| [checked_image_type](../app_security.py#L45) | función | 45 |
| [public_error](../app_security.py#L71) | función | 71 |
| [WindowLimiter](../app_security.py#L83) | clase | 83 |
| [__init__](../app_security.py#L85) | función | 85 |
| [allow](../app_security.py#L91) | función | 91 |
| [SecurityMiddleware](../app_security.py#L108) | clase | 108 |
| [__init__](../app_security.py#L110) | función | 110 |
| [__call__](../app_security.py#L119) | async | 119 |
| [secure_send](../app_security.py#L133) | async | 133 |
| [buffered](../app_security.py#L210) | async | 210 |

## catalog_capture.py

| Objeto | Tipo | Línea |
|---|---|---|
| [text](../catalog_capture.py#L15) | función | 15 |
| [normalized](../catalog_capture.py#L22) | función | 22 |
| [barcode](../catalog_capture.py#L28) | función | 28 |
| [barcode_key](../catalog_capture.py#L42) | función | 42 |
| [record_barcode](../catalog_capture.py#L50) | función | 50 |
| [family_name](../catalog_capture.py#L68) | función | 68 |
| [presentation](../catalog_capture.py#L73) | función | 73 |
| [same_brand](../catalog_capture.py#L87) | función | 87 |
| [family_label](../catalog_capture.py#L99) | función | 99 |
| [family_score](../catalog_capture.py#L105) | función | 105 |
| [find_duplicate](../catalog_capture.py#L117) | función | 117 |
| [review_product](../catalog_capture.py#L157) | función | 157 |
| [next_parent_sku](../catalog_capture.py#L184) | función | 184 |
| [records_from_values](../catalog_capture.py#L212) | función | 212 |
| [prepare_capture_updates](../catalog_capture.py#L224) | función | 224 |

## catalog_platform/accounts.py

| Objeto | Tipo | Línea |
|---|---|---|
| [account](../catalog_platform/accounts.py#L13) | función | 13 |
| [put](../catalog_platform/accounts.py#L21) | función | 21 |
| [gemini_for](../catalog_platform/accounts.py#L33) | función | 33 |
| [profile_tenant](../catalog_platform/accounts.py#L41) | función | 41 |
| [save_gemini](../catalog_platform/accounts.py#L46) | función | 46 |
| [save_profile](../catalog_platform/accounts.py#L54) | función | 54 |
| [delete_gemini](../catalog_platform/accounts.py#L61) | función | 61 |
| [restore](../catalog_platform/accounts.py#L67) | función | 67 |
| [persist](../catalog_platform/accounts.py#L102) | función | 102 |
| [load](../catalog_platform/accounts.py#L115) | función | 115 |

## catalog_platform/api.py

| Objeto | Tipo | Línea |
|---|---|---|
| [context](../catalog_platform/api.py#L29) | función | 29 |
| [tenant](../catalog_platform/api.py#L79) | función | 79 |
| [actor](../catalog_platform/api.py#L84) | función | 84 |
| [edit](../catalog_platform/api.py#L89) | función | 89 |
| [admin](../catalog_platform/api.py#L94) | función | 94 |
| [ProductInput](../catalog_platform/api.py#L100) | clase | 100 |
| [bounded_attributes](../catalog_platform/api.py#L123) | función | 123 |
| [bounded_tags](../catalog_platform/api.py#L141) | función | 141 |
| [BatchInput](../catalog_platform/api.py#L148) | clase | 148 |
| [EnqueueInput](../catalog_platform/api.py#L164) | clase | 164 |
| [ReviewInput](../catalog_platform/api.py#L171) | clase | 171 |
| [CorrectionInput](../catalog_platform/api.py#L179) | clase | 179 |
| [StockInput](../catalog_platform/api.py#L186) | clase | 186 |
| [ConfirmInput](../catalog_platform/api.py#L194) | clase | 194 |
| [DeleteProductInput](../catalog_platform/api.py#L199) | clase | 199 |
| [CancelJobsInput](../catalog_platform/api.py#L205) | clase | 205 |
| [status](../catalog_platform/api.py#L212) | función | 212 |
| [products](../catalog_platform/api.py#L253) | función | 253 |
| [create_product](../catalog_platform/api.py#L310) | función | 310 |
| [get_product](../catalog_platform/api.py#L333) | función | 333 |
| [related](../catalog_platform/api.py#L337) | función | 337 |
| [update_product](../catalog_platform/api.py#L373) | función | 373 |
| [delete_product](../catalog_platform/api.py#L395) | función | 395 |
| [inventory_change](../catalog_platform/api.py#L437) | función | 437 |
| [ReferenceInput](../catalog_platform/api.py#L467) | clase | 467 |
| [reference](../catalog_platform/api.py#L473) | función | 473 |
| [image](../catalog_platform/api.py#L528) | función | 528 |
| [selection](../catalog_platform/api.py#L559) | función | 559 |
| [image_unit](../catalog_platform/api.py#L614) | función | 614 |
| [estimate](../catalog_platform/api.py#L632) | función | 632 |
| [guard_cost](../catalog_platform/api.py#L664) | función | 664 |
| [generation_estimate](../catalog_platform/api.py#L682) | función | 682 |
| [enqueue](../catalog_platform/api.py#L690) | función | 690 |
| [batches](../catalog_platform/api.py#L780) | función | 780 |
| [jobs](../catalog_platform/api.py#L796) | función | 796 |
| [cancel_locked](../catalog_platform/api.py#L813) | función | 813 |
| [cancel_job](../catalog_platform/api.py#L830) | función | 830 |
| [cancel_jobs](../catalog_platform/api.py#L848) | función | 848 |
| [assets](../catalog_platform/api.py#L864) | función | 864 |
| [review](../catalog_platform/api.py#L889) | función | 889 |
| [correct](../catalog_platform/api.py#L949) | función | 949 |
| [RegenerationInput](../catalog_platform/api.py#L1021) | clase | 1021 |
| [regenerate](../catalog_platform/api.py#L1028) | función | 1028 |
| [OperationInput](../catalog_platform/api.py#L1052) | clase | 1052 |
| [save_generated_asset](../catalog_platform/api.py#L1060) | función | 1060 |
| [dashboard](../catalog_platform/api.py#L1079) | función | 1079 |
| [count](../catalog_platform/api.py#L1082) | función | 1082 |
| [events](../catalog_platform/api.py#L1120) | función | 1120 |
| [connections](../catalog_platform/api.py#L1137) | función | 1137 |
| [enqueue_operation](../catalog_platform/api.py#L1153) | función | 1153 |
| [preview_sheet](../catalog_platform/api.py#L1217) | función | 1217 |
| [preview_file](../catalog_platform/api.py#L1247) | async | 1247 |
| [ImportConfirm](../catalog_platform/api.py#L1281) | clase | 1281 |
| [commit_import](../catalog_platform/api.py#L1287) | función | 1287 |
| [RetryInput](../catalog_platform/api.py#L1342) | clase | 1342 |
| [retry](../catalog_platform/api.py#L1349) | función | 1349 |
| [reference_from_image](../catalog_platform/api.py#L1379) | función | 1379 |
| [export](../catalog_platform/api.py#L1426) | función | 1426 |
| [enrich_product](../catalog_platform/api.py#L1480) | función | 1480 |
| [barcode](../catalog_platform/api.py#L1515) | función | 1515 |
| [approve_original](../catalog_platform/api.py#L1525) | función | 1525 |
| [change_archive](../catalog_platform/api.py#L1575) | función | 1575 |
| [archive_product](../catalog_platform/api.py#L1629) | función | 1629 |
| [restore_product](../catalog_platform/api.py#L1634) | función | 1634 |

## catalog_platform/backup.py

| Objeto | Tipo | Línea |
|---|---|---|
| [main](../catalog_platform/backup.py#L13) | función | 13 |

## catalog_platform/capture_bridge.py

| Objeto | Tipo | Línea |
|---|---|---|
| [root_for](../catalog_platform/capture_bridge.py#L29) | función | 29 |
| [active](../catalog_platform/capture_bridge.py#L34) | función | 34 |
| [sheet_write_guard](../catalog_platform/capture_bridge.py#L41) | función | 41 |
| [candidate](../catalog_platform/capture_bridge.py#L52) | función | 52 |
| [master_rows](../catalog_platform/capture_bridge.py#L59) | función | 59 |
| [check](../catalog_platform/capture_bridge.py#L84) | función | 84 |
| [checkpoint](../catalog_platform/capture_bridge.py#L112) | función | 112 |
| [store_path](../catalog_platform/capture_bridge.py#L125) | función | 125 |
| [mark_saved](../catalog_platform/capture_bridge.py#L155) | función | 155 |
| [restore](../catalog_platform/capture_bridge.py#L175) | función | 175 |
| [local](../catalog_platform/capture_bridge.py#L192) | función | 192 |
| [clear](../catalog_platform/capture_bridge.py#L220) | función | 220 |
| [recover_saved](../catalog_platform/capture_bridge.py#L231) | función | 231 |
| [event_id](../catalog_platform/capture_bridge.py#L250) | función | 250 |
| [mirror_records](../catalog_platform/capture_bridge.py#L255) | función | 255 |
| [mirror](../catalog_platform/capture_bridge.py#L330) | función | 330 |
| [pending](../catalog_platform/capture_bridge.py#L354) | función | 354 |

## catalog_platform/catalog.py

| Objeto | Tipo | Línea |
|---|---|---|
| [serialize](../catalog_platform/catalog.py#L33) | función | 33 |
| [product_for](../catalog_platform/catalog.py#L47) | función | 47 |
| [audit](../catalog_platform/catalog.py#L58) | función | 58 |
| [move_stock](../catalog_platform/catalog.py#L84) | función | 84 |
| [save_product](../catalog_platform/catalog.py#L128) | función | 128 |
| [csv_export](../catalog_platform/catalog.py#L238) | función | 238 |

## catalog_platform/database.py

| Objeto | Tipo | Línea |
|---|---|---|
| [configured](../catalog_platform/database.py#L13) | función | 13 |
| [engine_for](../catalog_platform/database.py#L20) | función | 20 |
| [mark_process](../catalog_platform/database.py#L41) | función | 41 |
| [require_own_connection](../catalog_platform/database.py#L47) | función | 47 |
| [transaction](../catalog_platform/database.py#L60) | función | 60 |

## catalog_platform/enrichment.py

| Objeto | Tipo | Línea |
|---|---|---|
| [enrich](../catalog_platform/enrichment.py#L15) | función | 15 |

## catalog_platform/imports.py

| Objeto | Tipo | Línea |
|---|---|---|
| [normalize](../catalog_platform/imports.py#L19) | función | 19 |
| [number](../catalog_platform/imports.py#L64) | función | 64 |
| [parse_file](../catalog_platform/imports.py#L112) | función | 112 |
| [backup_catalog](../catalog_platform/imports.py#L152) | función | 152 |
| [execute_import](../catalog_platform/imports.py#L176) | función | 176 |
| [attach_historic_images](../catalog_platform/imports.py#L262) | función | 262 |

## catalog_platform/initialize.py

| Objeto | Tipo | Línea |
|---|---|---|
| [initialize_empty_database](../catalog_platform/initialize.py#L13) | función | 13 |

## catalog_platform/migrate.py

| Objeto | Tipo | Línea |
|---|---|---|
| [main](../catalog_platform/migrate.py#L13) | función | 13 |

## catalog_platform/models.py

| Objeto | Tipo | Línea |
|---|---|---|
| [uid](../catalog_platform/models.py#L23) | función | 23 |
| [now](../catalog_platform/models.py#L28) | función | 28 |
| [Base](../catalog_platform/models.py#L33) | clase | 33 |
| [Record](../catalog_platform/models.py#L39) | clase | 39 |
| [Product](../catalog_platform/models.py#L47) | clase | 47 |
| [ProductVariant](../catalog_platform/models.py#L93) | clase | 93 |
| [ProductImage](../catalog_platform/models.py#L103) | clase | 103 |
| [Category](../catalog_platform/models.py#L121) | clase | 121 |
| [Brand](../catalog_platform/models.py#L128) | clase | 128 |
| [InventoryMovement](../catalog_platform/models.py#L136) | clase | 136 |
| [GenerationBatch](../catalog_platform/models.py#L155) | clase | 155 |
| [GenerationJob](../catalog_platform/models.py#L167) | clase | 167 |
| [GeneratedAsset](../catalog_platform/models.py#L202) | clase | 202 |
| [IntegrationAccount](../catalog_platform/models.py#L224) | clase | 224 |
| [IntegrationMapping](../catalog_platform/models.py#L238) | clase | 238 |
| [SyncEvent](../catalog_platform/models.py#L251) | clase | 251 |
| [WebhookEvent](../catalog_platform/models.py#L265) | clase | 265 |
| [AuditLog](../catalog_platform/models.py#L285) | clase | 285 |
| [WorkerHeartbeat](../catalog_platform/models.py#L298) | clase | 298 |
| [OrderSnapshot](../catalog_platform/models.py#L307) | clase | 307 |

## catalog_platform/queue.py

| Objeto | Tipo | Línea |
|---|---|---|
| [JobCancelled](../catalog_platform/queue.py#L14) | clase | 14 |
| [mark_cancelled](../catalog_platform/queue.py#L20) | función | 20 |
| [request_cancel](../catalog_platform/queue.py#L34) | función | 34 |
| [request_lock](../catalog_platform/queue.py#L48) | función | 48 |
| [heartbeat](../catalog_platform/queue.py#L60) | función | 60 |
| [worker_ready](../catalog_platform/queue.py#L76) | función | 76 |
| [available](../catalog_platform/queue.py#L94) | función | 94 |
| [dispatch](../catalog_platform/queue.py#L105) | función | 105 |
| [recover_expired](../catalog_platform/queue.py#L113) | función | 113 |
| [claim](../catalog_platform/queue.py#L136) | función | 136 |
| [checkpoint](../catalog_platform/queue.py#L172) | función | 172 |
| [renew](../catalog_platform/queue.py#L207) | función | 207 |
| [finish](../catalog_platform/queue.py#L218) | función | 218 |

## catalog_platform/rbac.py

| Objeto | Tipo | Línea |
|---|---|---|
| [RoleMiddleware](../catalog_platform/rbac.py#L11) | clase | 11 |
| [__init__](../catalog_platform/rbac.py#L13) | función | 13 |
| [__call__](../catalog_platform/rbac.py#L18) | async | 18 |

## catalog_platform/redis_broker.py

| Objeto | Tipo | Línea |
|---|---|---|
| [connection_for](../catalog_platform/redis_broker.py#L24) | función | 24 |
| [connection](../catalog_platform/redis_broker.py#L32) | función | 32 |
| [reachable](../catalog_platform/redis_broker.py#L40) | función | 40 |
| [rq_queue](../catalog_platform/redis_broker.py#L48) | función | 48 |
| [publish_one](../catalog_platform/redis_broker.py#L53) | función | 53 |
| [publish_committed](../catalog_platform/redis_broker.py#L85) | función | 85 |
| [reconcile](../catalog_platform/redis_broker.py#L99) | función | 99 |

## catalog_platform/redis_worker.py

| Objeto | Tipo | Línea |
|---|---|---|
| [concurrency](../catalog_platform/redis_worker.py#L19) | función | 19 |
| [main](../catalog_platform/redis_worker.py#L31) | función | 31 |
| [shutdown](../catalog_platform/redis_worker.py#L51) | función | 51 |

## catalog_platform/render_config.py

| Objeto | Tipo | Línea |
|---|---|---|
| [configure_redirect](../catalog_platform/render_config.py#L11) | función | 11 |

## catalog_platform/security.py

| Objeto | Tipo | Línea |
|---|---|---|
| [cipher](../catalog_platform/security.py#L11) | función | 11 |
| [seal](../catalog_platform/security.py#L26) | función | 26 |
| [unseal](../catalog_platform/security.py#L31) | función | 31 |
| [role_for](../catalog_platform/security.py#L42) | función | 42 |
| [member](../catalog_platform/security.py#L58) | función | 58 |
| [require_role](../catalog_platform/security.py#L72) | función | 72 |

## catalog_platform/studio_jobs.py

| Objeto | Tipo | Línea |
|---|---|---|
| [enabled](../catalog_platform/studio_jobs.py#L21) | función | 21 |
| [tenant_for](../catalog_platform/studio_jobs.py#L26) | función | 26 |
| [public_job](../catalog_platform/studio_jobs.py#L35) | función | 35 |
| [find_active](../catalog_platform/studio_jobs.py#L42) | función | 42 |
| [recorded_usage](../catalog_platform/studio_jobs.py#L57) | función | 57 |
| [enqueue_capture](../catalog_platform/studio_jobs.py#L76) | función | 76 |
| [process_capture](../catalog_platform/studio_jobs.py#L143) | función | 143 |
| [restore](../catalog_platform/studio_jobs.py#L209) | función | 209 |
| [get_job](../catalog_platform/studio_jobs.py#L245) | función | 245 |
| [recover_latest](../catalog_platform/studio_jobs.py#L262) | función | 262 |
| [record_saved](../catalog_platform/studio_jobs.py#L286) | función | 286 |
| [record_approval](../catalog_platform/studio_jobs.py#L307) | función | 307 |

## catalog_platform/web_sessions.py

| Objeto | Tipo | Línea |
|---|---|---|
| [_tenant](../catalog_platform/web_sessions.py#L24) | función | 24 |
| [save](../catalog_platform/web_sessions.py#L32) | función | 32 |
| [revoke](../catalog_platform/web_sessions.py#L44) | función | 44 |
| [restore](../catalog_platform/web_sessions.py#L55) | función | 55 |

## catalog_platform/worker.py

| Objeto | Tipo | Línea |
|---|---|---|
| [download_reference](../catalog_platform/worker.py#L30) | función | 30 |
| [file_checksum](../catalog_platform/worker.py#L39) | función | 39 |
| [candidate_folder](../catalog_platform/worker.py#L48) | función | 48 |
| [record_usage](../catalog_platform/worker.py#L53) | función | 53 |
| [generation](../catalog_platform/worker.py#L68) | función | 68 |
| [progress](../catalog_platform/worker.py#L98) | función | 98 |
| [save_asset](../catalog_platform/worker.py#L275) | función | 275 |
| [process](../catalog_platform/worker.py#L306) | función | 306 |
| [execute_job](../catalog_platform/worker.py#L373) | función | 373 |
| [renew](../catalog_platform/worker.py#L379) | función | 379 |
| [main](../catalog_platform/worker.py#L421) | función | 421 |
| [keeper](../catalog_platform/worker.py#L441) | función | 441 |

## catalog_platform/worker_wakeup.py

| Objeto | Tipo | Línea |
|---|---|---|
| [health_url](../catalog_platform/worker_wakeup.py#L20) | función | 20 |
| [configured](../catalog_platform/worker_wakeup.py#L35) | función | 35 |
| [notify](../catalog_platform/worker_wakeup.py#L43) | función | 43 |
| [_wake](../catalog_platform/worker_wakeup.py#L65) | función | 65 |

## catalog_platform/worker_web.py

| Objeto | Tipo | Línea |
|---|---|---|
| [health_server](../catalog_platform/worker_web.py#L14) | función | 14 |
| [HealthHandler](../catalog_platform/worker_web.py#L15) | clase | 15 |
| [setup](../catalog_platform/worker_web.py#L16) | función | 16 |
| [do_GET](../catalog_platform/worker_web.py#L20) | función | 20 |
| [log_message](../catalog_platform/worker_web.py#L36) | función | 36 |
| [main](../catalog_platform/worker_web.py#L44) | función | 44 |

## catalog_taxonomy.py

| Objeto | Tipo | Línea |
|---|---|---|
| [read_rows](../catalog_taxonomy.py#L12) | función | 12 |
| [classification](../catalog_taxonomy.py#L42) | función | 42 |
| [choices_from_rows](../catalog_taxonomy.py#L49) | función | 49 |

## creative_pipeline.py

| Objeto | Tipo | Línea |
|---|---|---|
| [product_data](../creative_pipeline.py#L31) | función | 31 |
| [interaction_for](../creative_pipeline.py#L37) | función | 37 |
| [has](../creative_pipeline.py#L48) | función | 48 |
| [fallback_brief](../creative_pipeline.py#L65) | función | 65 |
| [grounding](../creative_pipeline.py#L82) | función | 82 |
| [brief](../creative_pipeline.py#L98) | función | 98 |
| [plan_key](../creative_pipeline.py#L140) | función | 140 |
| [load_style_examples](../creative_pipeline.py#L145) | función | 145 |
| [image_config](../creative_pipeline.py#L186) | función | 186 |
| [image_contents](../creative_pipeline.py#L191) | función | 191 |
| [extract_image](../creative_pipeline.py#L210) | función | 210 |
| [generate](../creative_pipeline.py#L220) | función | 220 |

## drive_image_index.py

| Objeto | Tipo | Línea |
|---|---|---|
| [parse_image_names](../drive_image_index.py#L8) | función | 8 |
| [list_drive_images](../drive_image_index.py#L12) | función | 12 |
| [fallback_names](../drive_image_index.py#L39) | función | 39 |
| [resolve_product_images](../drive_image_index.py#L50) | función | 50 |

## drive_service.py

| Objeto | Tipo | Línea |
|---|---|---|
| [DriveService](../drive_service.py#L9) | clase | 9 |
| [__init__](../drive_service.py#L10) | función | 10 |
| [files](../drive_service.py#L13) | función | 13 |
| [for_session](../drive_service.py#L18) | función | 18 |
| [list](../drive_service.py#L25) | función | 25 |
| [folder](../drive_service.py#L53) | función | 53 |
| [working_folder](../drive_service.py#L81) | función | 81 |
| [owns](../drive_service.py#L87) | función | 87 |
| [download](../drive_service.py#L111) | función | 111 |
| [_download](../drive_service.py#L118) | función | 118 |
| [download_to](../drive_service.py#L128) | función | 128 |
| [metadata](../drive_service.py#L141) | función | 141 |
| [find](../drive_service.py#L147) | función | 147 |
| [url](../drive_service.py#L152) | función | 152 |
| [save_approved](../drive_service.py#L157) | función | 157 |
| [upload](../drive_service.py#L181) | función | 181 |
| [backup](../drive_service.py#L200) | función | 200 |
| [upload_bytes](../drive_service.py#L215) | función | 215 |
| [export](../drive_service.py#L231) | función | 231 |

## frontend_host.py

| Objeto | Tipo | Línea |
|---|---|---|
| [register_frontend](../frontend_host.py#L7) | función | 7 |
| [manifest](../frontend_host.py#L15) | función | 15 |
| [service_worker](../frontend_host.py#L19) | función | 19 |
| [index](../frontend_host.py#L23) | función | 23 |
| [logo](../frontend_host.py#L29) | función | 29 |
| [studio](../frontend_host.py#L33) | función | 33 |
| [old_logout](../frontend_host.py#L37) | función | 37 |

## gemini_gateway.py

| Objeto | Tipo | Línea |
|---|---|---|
| [text_config](../gemini_gateway.py#L21) | función | 21 |
| [image_part](../gemini_gateway.py#L35) | función | 35 |
| [parse_json](../gemini_gateway.py#L50) | función | 50 |
| [usage_for_key](../gemini_gateway.py#L66) | función | 66 |
| [_fingerprint](../gemini_gateway.py#L74) | función | 74 |
| [_reserve](../gemini_gateway.py#L86) | función | 86 |
| [GeminiClient](../gemini_gateway.py#L105) | clase | 105 |
| [__init__](../gemini_gateway.py#L106) | función | 106 |
| [generate_content](../gemini_gateway.py#L111) | función | 111 |

## google_credentials.py

| Objeto | Tipo | Línea |
|---|---|---|
| [dedicated_credentials](../google_credentials.py#L8) | función | 8 |

## image_generation_service.py

| Objeto | Tipo | Línea |
|---|---|---|
| [ImageProvider](../image_generation_service.py#L8) | clase | 8 |
| [generate](../image_generation_service.py#L12) | función | 12 |
| [GeminiProvider](../image_generation_service.py#L15) | clase | 15 |
| [generate](../image_generation_service.py#L19) | función | 19 |
| [UnconfiguredProvider](../image_generation_service.py#L23) | clase | 23 |
| [generate](../image_generation_service.py#L24) | función | 24 |
| [FluxProvider](../image_generation_service.py#L30) | clase | 30 |
| [OpenAIProvider](../image_generation_service.py#L34) | clase | 34 |
| [PhotoRoomProvider](../image_generation_service.py#L38) | clase | 38 |
| [ImageGenerationService](../image_generation_service.py#L42) | clase | 42 |
| [__init__](../image_generation_service.py#L47) | función | 47 |
| [plan](../image_generation_service.py#L51) | función | 51 |
| [generate](../image_generation_service.py#L56) | función | 56 |

## inventory_bulk.py

| Objeto | Tipo | Línea |
|---|---|---|
| [counted_initial_skus](../inventory_bulk.py#L26) | función | 26 |
| [register_initial_counts](../inventory_bulk.py#L36) | función | 36 |

## inventory_operations.py

| Objeto | Tipo | Línea |
|---|---|---|
| [serialized_stock_write](../inventory_operations.py#L50) | función | 50 |
| [locked](../inventory_operations.py#L52) | función | 52 |
| [stock_integer](../inventory_operations.py#L58) | función | 58 |
| [_clean_text](../inventory_operations.py#L70) | función | 70 |
| [_search_key](../inventory_operations.py#L74) | función | 74 |
| [_cell_value](../inventory_operations.py#L80) | función | 80 |
| [_sheet_map](../inventory_operations.py#L88) | función | 88 |
| [ensure_movements_sheet](../inventory_operations.py#L99) | función | 99 |
| [read_inventory](../inventory_operations.py#L159) | función | 159 |
| [search_inventory](../inventory_operations.py#L179) | función | 179 |
| [inventory_table](../inventory_operations.py#L197) | función | 197 |
| [inventory_summary](../inventory_operations.py#L211) | función | 211 |
| [_find_unique_sku](../inventory_operations.py#L229) | función | 229 |
| [read_movements](../inventory_operations.py#L239) | función | 239 |
| [movements_table](../inventory_operations.py#L261) | función | 261 |
| [register_movement](../inventory_operations.py#L279) | función | 279 |

## inventory_schema.py

| Objeto | Tipo | Línea |
|---|---|---|
| [is_variable_parent](../inventory_schema.py#L18) | función | 18 |
| [split_category_path](../inventory_schema.py#L26) | función | 26 |
| [join_category_path](../inventory_schema.py#L34) | función | 34 |
| [normalize_product_row](../inventory_schema.py#L42) | función | 42 |
| [ProductKindIndex](../inventory_schema.py#L91) | clase | 91 |
| [from_rows](../inventory_schema.py#L96) | función | 96 |
| [collect](../inventory_schema.py#L97) | función | 97 |
| [kind_for](../inventory_schema.py#L105) | función | 105 |

## native_tools.py

| Objeto | Tipo | Línea |
|---|---|---|
| [movements](../native_tools.py#L20) | función | 20 |
| [inventory](../native_tools.py#L35) | función | 35 |
| [execute](../native_tools.py#L50) | async | 50 |
| [read](../native_tools.py#L57) | función | 57 |
| [register](../native_tools.py#L65) | función | 65 |
| [tools](../native_tools.py#L68) | async | 68 |
| [inventory_context](../native_tools.py#L103) | función | 103 |

## oauth_guard.py

| Objeto | Tipo | Línea |
|---|---|---|
| [issue_oauth](../oauth_guard.py#L16) | función | 16 |
| [consume_oauth](../oauth_guard.py#L29) | función | 29 |
| [email_allowed](../oauth_guard.py#L40) | función | 40 |

## product_capture.py

| Objeto | Tipo | Línea |
|---|---|---|
| [field_update](../product_capture.py#L13) | función | 13 |
| [read_barcodes](../product_capture.py#L27) | función | 27 |
| [compose_family_cover](../product_capture.py#L49) | función | 49 |
| [ProductCapture](../product_capture.py#L72) | clase | 72 |
| [__init__](../product_capture.py#L73) | función | 73 |
| [session](../product_capture.py#L77) | función | 77 |
| [snapshot](../product_capture.py#L83) | función | 83 |
| [check](../product_capture.py#L92) | función | 92 |
| [scan](../product_capture.py#L114) | función | 114 |
| [detect_from_product](../product_capture.py#L125) | función | 125 |
| [load_parents](../product_capture.py#L136) | función | 136 |
| [select_parent](../product_capture.py#L163) | función | 163 |
| [_namespace](../product_capture.py#L171) | función | 171 |
| [_references](../product_capture.py#L174) | función | 174 |
| [stage_image](../product_capture.py#L181) | función | 181 |
| [draft_images](../product_capture.py#L195) | función | 195 |
| [_drive_picture](../product_capture.py#L209) | función | 209 |
| [cover](../product_capture.py#L228) | función | 228 |
| [regenerate_cover](../product_capture.py#L288) | función | 288 |
| [save](../product_capture.py#L298) | función | 298 |

## product_generation.py

| Objeto | Tipo | Línea |
|---|---|---|
| [clean_description](../product_generation.py#L19) | función | 19 |
| [branded_image](../product_generation.py#L40) | función | 40 |

## retired_service.py

| Objeto | Tipo | Línea |
|---|---|---|
| [health](../retired_service.py#L19) | función | 19 |
| [retired](../retired_service.py#L26) | función | 26 |

## service_entrypoint.py

| Objeto | Tipo | Línea |
|---|---|---|
| [service_health](../service_entrypoint.py#L25) | función | 25 |

## sheet_inventory.py

| Objeto | Tipo | Línea |
|---|---|---|
| [_read_master_inventory](../sheet_inventory.py#L15) | función | 15 |
| [_session](../sheet_inventory.py#L38) | función | 38 |
| [_context](../sheet_inventory.py#L43) | función | 43 |
| [inventory_count_bulk](../sheet_inventory.py#L54) | async | 54 |
| [inventory_movement](../sheet_inventory.py#L75) | async | 75 |

## sheets_service.py

| Objeto | Tipo | Línea |
|---|---|---|
| [column_name](../sheets_service.py#L6) | función | 6 |
| [SheetsService](../sheets_service.py#L14) | clase | 14 |
| [__init__](../sheets_service.py#L15) | función | 15 |
| [spreadsheets](../sheets_service.py#L18) | función | 18 |
| [_id](../sheets_service.py#L22) | función | 22 |
| [_tab](../sheets_service.py#L27) | función | 27 |
| [metadata](../sheets_service.py#L30) | función | 30 |
| [read_range](../sheets_service.py#L34) | función | 34 |
| [columns](../sheets_service.py#L41) | función | 41 |
| [find_sku](../sheets_service.py#L57) | función | 57 |
| [update_cell](../sheets_service.py#L80) | función | 80 |

## studio_api.py

| Objeto | Tipo | Línea |
|---|---|---|
| [Product](../studio_api.py#L43) | clase | 43 |
| [Capture](../studio_api.py#L68) | clase | 68 |
| [CaptureNotes](../studio_api.py#L75) | clase | 75 |
| [Generation](../studio_api.py#L80) | clase | 80 |
| [Correction](../studio_api.py#L88) | clase | 88 |
| [Approval](../studio_api.py#L97) | clase | 97 |
| [Settings](../studio_api.py#L102) | clase | 102 |
| [Save](../studio_api.py#L108) | clase | 108 |
| [authenticated_session](../studio_api.py#L113) | función | 113 |
| [session](../studio_api.py#L121) | función | 121 |
| [editor](../studio_api.py#L132) | función | 132 |
| [ready](../studio_api.py#L140) | función | 140 |
| [draft](../studio_api.py#L146) | función | 146 |
| [idle](../studio_api.py#L154) | función | 154 |
| [asset](../studio_api.py#L164) | función | 164 |
| [file_path](../studio_api.py#L180) | función | 180 |
| [view](../studio_api.py#L190) | función | 190 |
| [error_message](../studio_api.py#L207) | función | 207 |
| [start_job](../studio_api.py#L228) | función | 228 |
| [update](../studio_api.py#L240) | función | 240 |
| [work](../studio_api.py#L245) | función | 245 |
| [session_status](../studio_api.py#L279) | función | 279 |
| [catalog_taxonomy](../studio_api.py#L317) | función | 317 |
| [settings](../studio_api.py#L330) | función | 330 |
| [remove_gemini](../studio_api.py#L384) | función | 384 |
| [test_gemini](../studio_api.py#L400) | función | 400 |
| [upload](../studio_api.py#L420) | async | 420 |
| [get_file](../studio_api.py#L439) | función | 439 |
| [capture](../studio_api.py#L447) | función | 447 |
| [update_product](../studio_api.py#L466) | función | 466 |
| [capture_notes](../studio_api.py#L497) | función | 497 |
| [clear_draft](../studio_api.py#L508) | función | 508 |
| [analyze](../studio_api.py#L517) | función | 517 |
| [action](../studio_api.py#L520) | función | 520 |
| [research_price](../studio_api.py#L592) | función | 592 |
| [action](../studio_api.py#L595) | función | 595 |
| [find_variants](../studio_api.py#L607) | función | 607 |
| [action](../studio_api.py#L609) | función | 609 |
| [creative_plan](../studio_api.py#L633) | función | 633 |
| [make_image](../studio_api.py#L648) | función | 648 |
| [generate_images](../studio_api.py#L679) | función | 679 |
| [action](../studio_api.py#L693) | función | 693 |
| [correct_image](../studio_api.py#L710) | función | 710 |
| [action](../studio_api.py#L726) | función | 726 |
| [approve](../studio_api.py#L736) | función | 736 |
| [check](../studio_api.py#L755) | función | 755 |
| [parents](../studio_api.py#L767) | función | 767 |
| [family_cover](../studio_api.py#L791) | función | 791 |
| [action](../studio_api.py#L793) | función | 793 |
| [save](../studio_api.py#L807) | función | 807 |
| [write](../studio_api.py#L815) | función | 815 |
| [action](../studio_api.py#L853) | función | 853 |
| [match_image](../studio_api.py#L863) | función | 863 |
| [repair_capture](../studio_api.py#L880) | función | 880 |
| [get_job](../studio_api.py#L890) | función | 890 |
| [catalog](../studio_api.py#L908) | función | 908 |
| [get_draft](../studio_api.py#L915) | función | 915 |
