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
      toastEnviada: "Enviada a anonimizar",
      toastEnviadaSub: "La IA está localizando y borrando los datos…",
      // resultado
      resAntes: "Original",
      resDespues: "Anonimizada",
      resTexto: "Texto detectado y eliminado",
      resSinTexto: "No se detectó texto identificable.",
      resDescargar: "Descargar imagen",
      resOtra: "Anonimizar otra",
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
      toastEnviada: "Sent for anonymizing",
      toastEnviadaSub: "The AI is locating and removing the data…",
      // resultado
      resAntes: "Original",
      resDespues: "Anonymized",
      resTexto: "Detected and removed text",
      resSinTexto: "No identifiable text was detected.",
      resDescargar: "Download image",
      resOtra: "Anonymize another",
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

  // Resultado
  const resultado     = document.getElementById("resultado");
  const resImgAntes   = document.getElementById("resImgAntes");
  const resImgDespues = document.getElementById("resImgDespues");
  const resLista      = document.getElementById("resLista");
  const resVacio      = document.getElementById("resVacio");
  const resContador   = document.getElementById("resContador");
  const resDescargar  = document.getElementById("resDescargar");
  const resOtra       = document.getElementById("resOtra");
  const capaCajas     = document.getElementById("cajas");

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

  // -- Procesar en el motor Python (al pulsar Anonimizar) --------------
  async function anonimizarEnServidor(archivo) {
    const datos = new FormData();
    datos.append("imagen", archivo);
    const r = await fetch("/anonimizar", { method: "POST", body: datos });
    const res = await r.json();
    if (!res || !res.ok) throw new Error((res && res.error) || "error");
    return res;
  }

  // -- Dibujar las cajas detectadas sobre la imagen del objetivo -------
  function dibujarCajas(cajas) {
    capaCajas.innerHTML = "";
    if (!Array.isArray(cajas)) return;
    cajas.forEach((c, i) => {
      const el = document.createElement("span");
      el.className = "caja-det";
      // posición en % (las coords vienen normalizadas 0..1)
      el.style.left = `${c.x * 100}%`;
      el.style.top = `${c.y * 100}%`;
      el.style.width = `${c.w * 100}%`;
      el.style.height = `${c.h * 100}%`;
      // aparición escalonada
      el.style.animationDelay = `${i * 0.08}s`;
      capaCajas.appendChild(el);
    });
  }

  // -- Pintar el resultado (comparación + cajas + texto) ---------------
  function mostrarResultado(res) {
    // imágenes antes / después
    resImgAntes.src = previa.src || "";
    resImgDespues.src = res.imagen;

    // la lente y la ficha desaparecen; manda el bloque de comparación
    objetivo.classList.remove("is-cargando");
    document.body.classList.add("tiene-resultado");

    // dibujar las cajas sobre la imagen Original (aparecen y se desvanecen)
    dibujarCajas(res.cajas || []);

    // enlace de descarga (nombre derivado del original)
    resDescargar.href = res.imagen;
    const base = (res.original || "imagen").replace(/\.[^.]+$/, "");
    resDescargar.download = `${base}_anonimizada.png`;

    // lista de textos detectados
    resLista.innerHTML = "";
    const lecturas = res.lecturas || [];
    if (lecturas.length === 0) {
      resVacio.hidden = false;
      resLista.hidden = true;
    } else {
      resVacio.hidden = true;
      resLista.hidden = false;
      lecturas.forEach((l) => {
        const li = document.createElement("li");
        li.textContent = l.texto;
        if (typeof l.score === "number") {
          const s = document.createElement("span");
          s.className = "puntuacion";
          s.textContent = `${Math.round(l.score * 100)}%`;
          li.appendChild(s);
        }
        resLista.appendChild(li);
      });
    }
    resContador.textContent = lecturas.length;

    resultado.hidden = false;
    resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // -- Reiniciar --------------------------------------------------------
  function reiniciar() {
    document.body.classList.remove("tiene-resultado");
    objetivo.classList.remove("has-imagen", "is-enfocando", "is-cargando");
    vista.setAttribute("aria-hidden", "true");
    previa.removeAttribute("src");
    if (capaCajas) capaCajas.innerHTML = "";
    ficha.hidden = true;
    metadatos.hidden = false;
    if (resultado) resultado.hidden = true;
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
  if (resOtra) resOtra.addEventListener("click", reiniciar);

  btnEnfocar.addEventListener("click", async () => {
    if (!archivoActual) return;

    // Aviso inmediato + animación de carga (diafragma cerrándose/abriendo)
    mostrarToast("toastEnviada", "toastEnviadaSub", "ok");
    document.body.classList.remove("tiene-resultado");
    objetivo.classList.remove("is-enfocando");
    objetivo.classList.add("is-cargando");
    capaCajas.innerHTML = "";

    btnEnfocar.disabled = true;
    ponerEstado("estGuardando");

    try {
      const res = await anonimizarEnServidor(archivoActual);
      guardado = true;
      ponerEstado("estGuardada", "ok");
      mostrarToast("toastGuardada", "toastGuardadaSub", "ok");
      mostrarResultado(res);
    } catch (err) {
      objetivo.classList.remove("is-cargando");
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
