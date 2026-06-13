/* ============================================================
   Objetivo — interacción de subida + idioma + notificaciones
   ============================================================ */

(() => {
  "use strict";

  // -- Textos en los dos idiomas ---------------------------------------
  const I18N = {
    es: {
      docTitle: "Anonimizador clínico",
      eyebrow: "Visión por imagen",
      titular: "Anonimizador clínico",
      entrada:
        "Arrastra o selecciona una imagen clínica en el objetivo y la IA se encargará de anonimizarla.",
      cambiar: "Cambiar imagen",
      enfocar: "Anonimizar",
      metaFormatos: "Formatos",
      metaLimite: "Límite",
      metaPrivacidad: "Privacidad",
      metaPrivacidadValor: "se procesa en tu equipo",
      // guía
      guiaVacioPrincipal: "Arrastra la imagen aquí",
      guiaVacioSecundario: "o pulsa para buscarla",
      guiaDragPrincipal: "Suelta para anonimizar",
      guiaDragSecundario: "te tengo",
      // estados
      estListo: "Listo para anonimizar",
      estCargada: "Imagen cargada",
      estGuardando: "Anonimizando…",
      estGuardada: "Imagen anonimizada",
      estNoImagen: "Eso no parece una imagen",
      estGrande: "La imagen supera los 10 MB",
      estErrorGuardar: "No se pudo procesar",
      // toast
      toastGuardada: "Imagen anonimizada",
      toastGuardadaSub: "Sin datos del paciente, lista para compartir.",
      toastError: "No se pudo procesar",
      toastErrorSub: "Revisa que el servidor esté en marcha.",
    },
    en: {
      docTitle: "Clinical anonymizer",
      eyebrow: "Image-based vision",
      titular: "Clinical anonymizer",
      entrada:
        "Drop or select a clinical image into the target area and the AI will take care of anonymizing it.",
      cambiar: "Change image",
      enfocar: "Anonymize",
      metaFormatos: "Formats",
      metaLimite: "Limit",
      metaPrivacidad: "Privacy",
      metaPrivacidadValor: "processed on your device",
      guiaVacioPrincipal: "Drop the image here",
      guiaVacioSecundario: "or click to browse",
      guiaDragPrincipal: "Drop to anonymize",
      guiaDragSecundario: "got it",
      estListo: "Ready to anonymize",
      estCargada: "Image loaded",
      estGuardando: "Anonymizing…",
      estGuardada: "Image anonymized",
      estNoImagen: "That doesn't look like an image",
      estGrande: "The image is over 10 MB",
      estErrorGuardar: "Couldn't process",
      toastGuardada: "Image anonymized",
      toastGuardadaSub: "No patient data, ready to share.",
      toastError: "Couldn't process",
      toastErrorSub: "Check that the server is running.",
    },
  };

  // -- Referencias al DOM ----------------------------------------------
  const objetivo    = document.getElementById("objetivo");
  const inputFile   = document.getElementById("archivo");
  const vista       = document.getElementById("vista");
  const previa      = document.getElementById("previa");
  const ficha       = document.getElementById("ficha");
  const fichaNombre = document.getElementById("fichaNombre");
  const fichaPeso   = document.getElementById("fichaPeso");
  const metadatos   = document.getElementById("metadatos");
  const btnCambiar  = document.getElementById("cambiar");
  const btnEnfocar  = document.getElementById("enfocar");
  const estado      = document.getElementById("estado");
  const estadoTexto = document.getElementById("estadoTexto");
  const guiaPrincipal  = document.getElementById("guiaPrincipal");
  const guiaSecundario = document.getElementById("guiaSecundario");
  const toast       = document.getElementById("toast");
  const botonesIdioma = document.querySelectorAll(".idiomas__btn");

  // -- Estado de la aplicación -----------------------------------------
  let idioma = localStorage.getItem("idioma") || (navigator.language || "es").slice(0, 2);
  if (!I18N[idioma]) idioma = "es";

  let archivoActual = null;     // el File pendiente de guardar
  let guardado = false;         // si ya se guardó en el servidor
  let claveEstado = "estListo"; // clave del estado actual (para retraducir)
  let toastTimer = null;

  const T = () => I18N[idioma];

  // -- Idioma -----------------------------------------------------------
  function aplicarIdioma(nuevo) {
    idioma = I18N[nuevo] ? nuevo : "es";
    localStorage.setItem("idioma", idioma);
    document.documentElement.lang = idioma;
    document.title = T().docTitle;

    // Textos estáticos marcados con data-i18n
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const clave = el.dataset.i18n;
      if (T()[clave] !== undefined) el.textContent = T()[clave];
    });

    // Botones del selector
    botonesIdioma.forEach((b) =>
      b.classList.toggle("is-activa", b.dataset.lang === idioma)
    );

    // Textos dinámicos según el estado actual
    if (estadoTexto) estadoTexto.textContent = T()[claveEstado] || "";
    refrescarGuia();
  }

  function refrescarGuia() {
    const arrastrando = objetivo.classList.contains("is-drag");
    guiaPrincipal.textContent = arrastrando ? T().guiaDragPrincipal : T().guiaVacioPrincipal;
    guiaSecundario.textContent = arrastrando ? T().guiaDragSecundario : T().guiaVacioSecundario;
  }

  // -- Utilidades -------------------------------------------------------
  function formatearPeso(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function ponerEstado(clave, tipo = "") {
    claveEstado = clave;
    if (estadoTexto) estadoTexto.textContent = T()[clave] || "";
    if (estado) {
      estado.classList.toggle("is-ok", tipo === "ok");
      estado.classList.toggle("is-error", tipo === "error");
    }
  }

  function mostrarToast(claveTitulo, claveSub, tipo = "ok") {
    toast.className = `toast is-${tipo}`;
    toast.hidden = false;
    toast.innerHTML = `
      <span class="toast__icono" aria-hidden="true">${tipo === "ok" ? "✓" : "!"}</span>
      <span class="toast__texto">
        <span>${T()[claveTitulo]}</span>
        <span class="toast__sub">${T()[claveSub]}</span>
      </span>`;
    // Forzar reflow para reiniciar la transición
    void toast.offsetWidth;
    toast.classList.add("is-visible");

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("is-visible");
      setTimeout(() => { toast.hidden = true; }, 350);
    }, 3200);
  }

  // -- Mostrar la imagen dentro del objetivo ---------------------------
  function mostrarImagen(archivo) {
    if (!archivo.type.startsWith("image/")) return ponerEstado("estNoImagen", "error");
    if (archivo.size > 10 * 1024 * 1024) return ponerEstado("estGrande", "error");

    archivoActual = archivo;
    guardado = false;

    const lector = new FileReader();
    lector.onload = (e) => {
      previa.src = e.target.result;
      objetivo.classList.add("has-imagen");
      vista.setAttribute("aria-hidden", "false");

      fichaNombre.textContent = archivo.name;
      fichaPeso.textContent = formatearPeso(archivo.size);
      ficha.hidden = false;
      metadatos.hidden = true;

      btnEnfocar.disabled = false;
      ponerEstado("estCargada", "ok");
    };
    lector.readAsDataURL(archivo);
  }

  // -- Guardar en el motor Python (al pulsar Enfocar) ------------------
  async function guardarEnServidor(archivo) {
    const datos = new FormData();
    datos.append("imagen", archivo);
    const r = await fetch("/upload", { method: "POST", body: datos });
    const res = await r.json();
    if (!res || !res.ok) throw new Error((res && res.error) || "error");
    return res;
  }

  // -- Reiniciar --------------------------------------------------------
  function reiniciar() {
    objetivo.classList.remove("has-imagen", "is-enfocando");
    vista.setAttribute("aria-hidden", "true");
    previa.removeAttribute("src");
    ficha.hidden = true;
    metadatos.hidden = false;
    inputFile.value = "";
    archivoActual = null;
    guardado = false;
    btnEnfocar.disabled = false;
    ponerEstado("estListo");
  }

  // -- Eventos: clic y teclado -----------------------------------------
  objetivo.addEventListener("click", () => {
    if (!objetivo.classList.contains("has-imagen")) inputFile.click();
  });

  objetivo.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && !objetivo.classList.contains("has-imagen")) {
      e.preventDefault();
      inputFile.click();
    }
  });

  inputFile.addEventListener("change", (e) => {
    const archivo = e.target.files[0];
    if (archivo) mostrarImagen(archivo);
  });

  // -- Eventos: arrastrar y soltar -------------------------------------
  ["dragenter", "dragover"].forEach((evt) =>
    objetivo.addEventListener(evt, (e) => {
      e.preventDefault();
      if (objetivo.classList.contains("has-imagen")) return;
      objetivo.classList.add("is-drag");
      refrescarGuia();
    })
  );

  ["dragleave", "dragend"].forEach((evt) =>
    objetivo.addEventListener(evt, (e) => {
      e.preventDefault();
      objetivo.classList.remove("is-drag");
      refrescarGuia();
    })
  );

  objetivo.addEventListener("drop", (e) => {
    e.preventDefault();
    objetivo.classList.remove("is-drag");
    refrescarGuia();
    const archivo = e.dataTransfer.files[0];
    if (archivo) mostrarImagen(archivo);
  });

  ["dragover", "drop"].forEach((evt) =>
    window.addEventListener(evt, (e) => e.preventDefault())
  );

  // -- Botones ----------------------------------------------------------
  btnCambiar.addEventListener("click", reiniciar);

  btnEnfocar.addEventListener("click", async () => {
    if (!archivoActual) return;

    // Animación de barrido de enfoque
    objetivo.classList.remove("is-enfocando");
    void objetivo.offsetWidth;
    objetivo.classList.add("is-enfocando");

    btnEnfocar.disabled = true;
    ponerEstado("estGuardando");

    try {
      await guardarEnServidor(archivoActual);
      guardado = true;
      ponerEstado("estGuardada", "ok");
      mostrarToast("toastGuardada", "toastGuardadaSub", "ok");
    } catch (err) {
      ponerEstado("estErrorGuardar", "error");
      mostrarToast("toastError", "toastErrorSub", "error");
    } finally {
      btnEnfocar.disabled = false;
    }
  });

  // -- Selector de idioma ----------------------------------------------
  botonesIdioma.forEach((b) =>
    b.addEventListener("click", () => aplicarIdioma(b.dataset.lang))
  );

  // -- Inicio -----------------------------------------------------------
  aplicarIdioma(idioma);
})();
