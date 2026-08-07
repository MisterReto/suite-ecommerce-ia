(() => {
    const inicializarTutorial = () => {
        if (window.__suiteEcommerceTutorialInicializado) return;
        window.__suiteEcommerceTutorialInicializado = true;

    const pasos = [
        {
            titulo: "Bienvenido a Suite Ecommerce",
            texto: "Este recorrido te enseñará el flujo completo: conectar tu cuenta, analizar un producto, revisar la información, generar fotografías y guardar el registro. Puedes salir cuando quieras y volver a abrirlo con el botón “Ver tutorial”."
        },
        {
            tab: "Configuración",
            selector: "#tour-config-intro",
            titulo: "1. Conecta tu Google Drive",
            texto: "Comienza conectando tu cuenta. La app usará tu propio Drive para leer categorías, guardar las imágenes y actualizar el inventario. El recuadro te indicará si la conexión está lista."
        },
        {
            tab: "Configuración",
            selector: "#tour-api-key",
            titulo: "2. Guarda tu API Key",
            texto: "Pega aquí tu API Key de Gemini y presiona “Guardar API Key”. Se mantiene únicamente durante tu sesión y permite realizar el análisis y la generación de imágenes."
        },
        {
            tab: "Configuración",
            selector: "#tour-folder",
            titulo: "3. Elige la carpeta (opcional)",
            texto: "Si no seleccionas una carpeta, se usará Proyecto_IA. También puedes pegar el enlace de otra carpeta de Drive para mantener todos los archivos en la ubicación que prefieras."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-upload-front",
            titulo: "4. Sube la fotografía del producto",
            texto: "Usa una foto frontal nítida y, si la tienes, agrega también la parte trasera. Procura que el empaque completo sea visible y que el texto pueda leerse."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-analyze",
            titulo: "5. Analiza el producto",
            texto: "Este botón identifica el producto y propone nombre, marca, medida, SKU, precio, categoría, etiquetas y descripciones SEO. Espera a que termine antes de continuar."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-product-name",
            titulo: "6. Revisa la información",
            texto: "La IA acelera la captura, pero tú mantienes el control. Revisa especialmente el nombre, la marca, la medida, el precio, el SKU, las categorías y las descripciones antes de guardar."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-product-type",
            titulo: "7. Elige Simple o Variable",
            texto: "Selecciona Simple cuando el producto no tenga otras presentaciones relacionadas. Usa Variable cuando comparta un producto padre con otros tamaños, gramajes o sabores."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-generate-photos",
            titulo: "8. Genera las fotografías comerciales",
            texto: "La app crea tres imágenes cuadradas: fondo blanco, lifestyle y comercial. Antes de generarlas, confirma que la foto original y la información del producto sean correctas."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-photo-feedback",
            titulo: "9. Corrige una imagen",
            texto: "Si la IA modifica el empaque, inventa un logo, cambia la escala o comete otro error, abre el panel de la imagen, selecciona el problema y presiona Rehacer. Las correcciones se acumulan por imagen."
        },
        {
            tab: "Ingreso y Edición de Productos",
            selector: "#tour-save-product",
            titulo: "10. Aprueba y guarda",
            texto: "Cuando los datos y las imágenes estén correctos, guarda el producto. El registro se añadirá a Gabo nueva y la app mantendrá sincronizada la Lista Variable cuando corresponda."
        },
        {
            tab: "Variantes de Presentación",
            selector: "#tour-lens-image",
            titulo: "11. Busca otras presentaciones",
            texto: "Esta pestaña funciona como una búsqueda visual: reutiliza la foto frontal o sube otra, busca tamaños o gramajes relacionados y aplica la recomendación de tipo al producto."
        },
        {
            titulo: "¡Recorrido terminado!",
            texto: "Ya conoces el flujo principal. El tutorial solamente se inicia cuando presionas el botón “VER TUTORIAL GUIADO”, así que puedes repetirlo todas las veces que quieras."
        }
    ];

    let indiceActual = 0;
    let activo = false;
    let objetivoActual = null;
    let temporizadorPosicion = null;

    const crearElemento = (etiqueta, id, clase) => {
        const elemento = document.createElement(etiqueta);
        if (id) elemento.id = id;
        if (clase) elemento.className = clase;
        return elemento;
    };

    const sombras = ["top", "left", "right", "bottom"].map((lado) => {
        const sombra = crearElemento("div", `suite-tour-shade-${lado}`, "suite-tour-shade");
        document.body.appendChild(sombra);
        return sombra;
    });

    const tarjeta = crearElemento("section", "suite-tour-card");
    tarjeta.setAttribute("role", "dialog");
    tarjeta.setAttribute("aria-modal", "true");
    tarjeta.setAttribute("aria-labelledby", "suite-tour-title");
    tarjeta.setAttribute("aria-live", "polite");
    tarjeta.innerHTML = `
        <button type="button" id="suite-tour-close" aria-label="Cerrar tutorial">×</button>
        <div id="suite-tour-step"></div>
        <h2 id="suite-tour-title"></h2>
        <p id="suite-tour-text"></p>
        <div id="suite-tour-progress" aria-hidden="true"><span></span></div>
        <div id="suite-tour-actions">
            <button type="button" id="suite-tour-skip">Saltar tutorial</button>
            <div>
                <button type="button" id="suite-tour-prev">Atrás</button>
                <button type="button" id="suite-tour-next">Siguiente</button>
            </div>
        </div>
    `;
    document.body.appendChild(tarjeta);

    const titulo = tarjeta.querySelector("#suite-tour-title");
    const texto = tarjeta.querySelector("#suite-tour-text");
    const indicador = tarjeta.querySelector("#suite-tour-step");
    const progreso = tarjeta.querySelector("#suite-tour-progress span");
    const btnAnterior = tarjeta.querySelector("#suite-tour-prev");
    const btnSiguiente = tarjeta.querySelector("#suite-tour-next");
    const btnSaltar = tarjeta.querySelector("#suite-tour-skip");
    const btnCerrar = tarjeta.querySelector("#suite-tour-close");

    const esperar = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
    const limitar = (valor, minimo, maximo) => Math.min(Math.max(valor, minimo), maximo);
    const normalizar = (valor) => (valor || "").replace(/\s+/g, " ").trim().toLowerCase();

    // Gradio puede usar DOM normal o una raíz Shadow DOM según la versión.
    // Todas las búsquedas del tutorial contemplan ambos casos.
    const obtenerRaices = () => {
        const raices = [document];
        const gradioApp = document.querySelector("gradio-app");
        if (gradioApp && gradioApp.shadowRoot) raices.push(gradioApp.shadowRoot);
        return raices;
    };

    const buscarElemento = (selector) => {
        for (const raiz of obtenerRaices()) {
            const elemento = raiz.querySelector(selector);
            if (elemento) return elemento;
        }
        return null;
    };

    const buscarElementos = (selector) => obtenerRaices()
        .flatMap((raiz) => Array.from(raiz.querySelectorAll(selector)));

    const asegurarEstilosEnShadowDom = () => {
        obtenerRaices().forEach((raiz) => {
            if (raiz === document || raiz.querySelector('link[data-suite-tutorial-css]')) return;
            const enlace = document.createElement("link");
            enlace.rel = "stylesheet";
            enlace.href = "/static/tutorial.css?v=2";
            enlace.dataset.suiteTutorialCss = "true";
            raiz.appendChild(enlace);
        });
    };

    const activarTab = (nombre) => {
        if (!nombre) return;
        const buscado = normalizar(nombre);
        const tabs = buscarElementos('[role="tab"]');
        const tab = tabs.find((elemento) => normalizar(elemento.textContent).includes(buscado));
        if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
    };

    const ocultarSombras = () => {
        sombras.forEach((sombra) => {
            sombra.style.display = "none";
        });
    };

    const rectanguloVisible = (elemento) => {
        if (!elemento) return null;
        const rect = elemento.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return null;
        return rect;
    };

    const colocarSombras = (rect) => {
        sombras.forEach((sombra) => { sombra.style.display = "block"; });

        if (!rect) {
            sombras[0].style.cssText = "display:block;position:fixed;inset:0;";
            sombras.slice(1).forEach((sombra) => { sombra.style.display = "none"; });
            return;
        }

        const margen = 10;
        const arriba = limitar(rect.top - margen, 0, window.innerHeight);
        const abajo = limitar(rect.bottom + margen, 0, window.innerHeight);
        const izquierda = limitar(rect.left - margen, 0, window.innerWidth);
        const derecha = limitar(rect.right + margen, 0, window.innerWidth);

        sombras[0].style.cssText = `display:block;position:fixed;left:0;top:0;width:100vw;height:${arriba}px;`;
        sombras[1].style.cssText = `display:block;position:fixed;left:0;top:${arriba}px;width:${izquierda}px;height:${Math.max(0, abajo - arriba)}px;`;
        sombras[2].style.cssText = `display:block;position:fixed;left:${derecha}px;top:${arriba}px;width:${Math.max(0, window.innerWidth - derecha)}px;height:${Math.max(0, abajo - arriba)}px;`;
        sombras[3].style.cssText = `display:block;position:fixed;left:0;top:${abajo}px;width:100vw;height:${Math.max(0, window.innerHeight - abajo)}px;`;
    };

    const colocarTarjeta = (rect) => {
        if (window.innerWidth <= 640) {
            tarjeta.style.left = "";
            tarjeta.style.right = "";
            tarjeta.style.top = "";
            tarjeta.style.bottom = "";
            return;
        }

        const ancho = Math.min(410, window.innerWidth - 32);
        const alto = tarjeta.offsetHeight || 320;
        const separacion = 18;

        if (!rect) {
            tarjeta.style.left = `${Math.max(16, (window.innerWidth - ancho) / 2)}px`;
            tarjeta.style.right = "auto";
            tarjeta.style.top = `${Math.max(16, (window.innerHeight - alto) / 2)}px`;
            tarjeta.style.bottom = "auto";
            return;
        }

        let left;
        let top;

        if (window.innerWidth - rect.right >= ancho + 36) {
            left = rect.right + separacion;
            top = limitar(rect.top, 16, window.innerHeight - alto - 16);
        } else if (rect.left >= ancho + 36) {
            left = rect.left - ancho - separacion;
            top = limitar(rect.top, 16, window.innerHeight - alto - 16);
        } else {
            left = limitar(rect.left, 16, window.innerWidth - ancho - 16);
            const espacioAbajo = window.innerHeight - rect.bottom;
            top = espacioAbajo >= alto + 24
                ? rect.bottom + separacion
                : rect.top - alto - separacion;
            top = limitar(top, 16, window.innerHeight - alto - 16);
        }

        tarjeta.style.left = `${left}px`;
        tarjeta.style.right = "auto";
        tarjeta.style.top = `${top}px`;
        tarjeta.style.bottom = "auto";
    };

    const actualizarPosicion = () => {
        if (!activo) return;
        const rect = rectanguloVisible(objetivoActual);
        colocarSombras(rect);
        colocarTarjeta(rect);
    };

    const programarPosicion = () => {
        window.clearTimeout(temporizadorPosicion);
        temporizadorPosicion = window.setTimeout(actualizarPosicion, 30);
    };

    const cerrar = () => {
        activo = false;
        document.documentElement.classList.remove("suite-tour-active");
        tarjeta.classList.remove("visible");
        ocultarSombras();
        if (objetivoActual) objetivoActual.classList.remove("suite-tour-target");
        objetivoActual = null;
    };

    const mostrarPaso = async (nuevoIndice) => {
        if (!activo) return;
        indiceActual = limitar(nuevoIndice, 0, pasos.length - 1);
        const paso = pasos[indiceActual];

        if (objetivoActual) objetivoActual.classList.remove("suite-tour-target");
        objetivoActual = null;
        activarTab(paso.tab);
        await esperar(paso.tab ? 260 : 30);

        if (paso.selector) {
            objetivoActual = buscarElemento(paso.selector);
            if (objetivoActual) {
                objetivoActual.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
                await esperar(360);
                objetivoActual.classList.add("suite-tour-target");
            }
        }

        indicador.textContent = `PASO ${indiceActual + 1} DE ${pasos.length}`;
        titulo.textContent = paso.titulo;
        texto.textContent = paso.texto;
        progreso.style.width = `${((indiceActual + 1) / pasos.length) * 100}%`;
        btnAnterior.disabled = indiceActual === 0;
        btnSiguiente.textContent = indiceActual === pasos.length - 1 ? "Terminar" : "Siguiente";
        tarjeta.classList.add("visible");
        actualizarPosicion();
        btnSiguiente.focus({ preventScroll: true });
    };

    const iniciar = () => {
        if (activo) return;
        activo = true;
        indiceActual = 0;
        document.documentElement.classList.add("suite-tour-active");
        mostrarPaso(0);
    };

    window.startSuiteEcommerceTutorial = iniciar;

    const lanzarDesdeBoton = (evento) => {
        evento.preventDefault();
        evento.stopPropagation();
        iniciar();
    };

    const conectarBotonTutorial = () => {
        asegurarEstilosEnShadowDom();
        const lanzador = buscarElemento("#tour-launcher");
        if (!lanzador) return false;

        if (lanzador.dataset.suiteTutorialConectado !== "true") {
            lanzador.dataset.suiteTutorialConectado = "true";
            lanzador.addEventListener("click", lanzarDesdeBoton);
        }
        return true;
    };

    // Respaldo delegado: composedPath conserva la ruta real del clic incluso
    // cuando el botón vive dentro del Shadow DOM de Gradio.
    document.addEventListener("click", (evento) => {
        const ruta = typeof evento.composedPath === "function" ? evento.composedPath() : [];
        const vieneDelLanzador = ruta.some((nodo) =>
            nodo instanceof Element
            && (nodo.id === "tour-launcher" || Boolean(nodo.closest?.("#tour-launcher")))
        );
        if (vieneDelLanzador) lanzarDesdeBoton(evento);
    }, true);

    // El montaje de Gradio es asíncrono. Se intenta conectar el botón hasta que
    // exista y luego se detiene el temporizador para no consumir recursos.
    let intentosConexion = 0;
    const temporizadorConexion = window.setInterval(() => {
        intentosConexion += 1;
        if (conectarBotonTutorial() || intentosConexion >= 120) {
            window.clearInterval(temporizadorConexion);
        }
    }, 250);
    conectarBotonTutorial();

    btnAnterior.addEventListener("click", () => mostrarPaso(indiceActual - 1));
    btnSiguiente.addEventListener("click", () => {
        if (indiceActual >= pasos.length - 1) cerrar();
        else mostrarPaso(indiceActual + 1);
    });
    btnSaltar.addEventListener("click", cerrar);
    btnCerrar.addEventListener("click", cerrar);

    window.addEventListener("resize", programarPosicion, { passive: true });
    window.addEventListener("scroll", programarPosicion, { passive: true, capture: true });
    document.addEventListener("keydown", (evento) => {
        if (!activo) return;
        if (evento.key === "Escape") cerrar();
        if (evento.key === "ArrowRight") {
            if (indiceActual >= pasos.length - 1) cerrar();
            else mostrarPaso(indiceActual + 1);
        }
        if (evento.key === "ArrowLeft") mostrarPaso(indiceActual - 1);
    });

    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicializarTutorial, { once: true });
    } else {
        inicializarTutorial();
    }
})();
