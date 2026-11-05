// Asistente de la versión web: el botón "?" y su chat.
// Las respuestas las arma el servidor (/asistente), con el mismo "cerebro" que la app de escritorio.
// La conversación se guarda en sessionStorage para que no se pierda al cambiar de pantalla.
(function () {
  const $ = (id) => document.getElementById(id);
  const boton = $("ayuda"), chat = $("chat"), mensajes = $("chat-mensajes"), atajos = $("chat-atajos");
  const form = $("chat-form"), texto = $("chat-texto");
  if (!boton) return;

  const CLAVE = "finanzapp-chat";
  let historial = leer();

  function leer() {
    try { return JSON.parse(sessionStorage.getItem(CLAVE)) || []; } catch (e) { return []; }
  }
  function guardar() {
    try { sessionStorage.setItem(CLAVE, JSON.stringify(historial.slice(-40))); } catch (e) { /* sin almacenamiento */ }
  }

  // ---------- Dibujar ----------
  function burbuja(m) {
    const fila = document.createElement("div");
    fila.className = "chat-fila " + (m.propia ? "propia" : "suya");
    const b = document.createElement("div");
    b.className = "burbuja";
    b.textContent = m.texto;               // textContent: nunca se interpreta como HTML
    fila.appendChild(b);
    (m.acciones || []).forEach((a) => {
      const enlace = document.createElement("a");
      enlace.className = "chat-accion";
      enlace.href = a.url;
      enlace.textContent = a.texto;
      fila.appendChild(enlace);
    });
    mensajes.appendChild(fila);
  }
  function mostrarAtajos(lista) {
    atajos.replaceChildren();
    (lista || []).slice(0, 4).forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = s;
      b.addEventListener("click", () => preguntar(s));
      atajos.appendChild(b);
    });
  }
  function dibujarTodo() {
    mensajes.replaceChildren();
    historial.forEach(burbuja);
    const ultima = [...historial].reverse().find((m) => !m.propia);
    mostrarAtajos(ultima ? ultima.sugerencias : []);
    mensajes.scrollTop = mensajes.scrollHeight;
  }

  // ---------- Hablar con el servidor ----------
  async function pedir(url, opciones) {
    const r = await fetch(url, opciones);
    if (r.status === 401) { location.href = "/login"; return null; }
    if (!r.ok) throw new Error("Error " + r.status);
    return r.json();
  }
  function agregarRespuesta(r) {
    if (!r) return;
    historial.push({ texto: r.texto, acciones: r.acciones, sugerencias: r.sugerencias });
    guardar();
    dibujarTodo();
  }
  async function saludar() {
    try { agregarRespuesta(await pedir("/asistente/bienvenida")); }
    catch (e) { agregarRespuesta({ texto: "No pude conectarme. Revisa que la computadora siga encendida.", acciones: [], sugerencias: [] }); }
  }
  async function preguntar(pregunta) {
    pregunta = (pregunta || "").trim();
    if (!pregunta) return;
    historial.push({ texto: pregunta, propia: true });
    guardar();
    dibujarTodo();
    try {
      agregarRespuesta(await pedir("/asistente", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto: pregunta }),
      }));
    } catch (e) {
      agregarRespuesta({ texto: "No pude responder ahora. Intenta de nuevo en un momento.", acciones: [], sugerencias: [] });
    }
  }

  // ---------- Abrir / cerrar / limpiar ----------
  function abrir() {
    chat.hidden = false;
    boton.setAttribute("aria-expanded", "true");
    if (!historial.length) saludar(); else dibujarTodo();
    setTimeout(() => texto.focus(), 50);
  }
  function cerrar() {
    chat.hidden = true;
    boton.setAttribute("aria-expanded", "false");
  }
  boton.addEventListener("click", () => (chat.hidden ? abrir() : cerrar()));
  $("chat-cerrar").addEventListener("click", cerrar);
  $("chat-limpiar").addEventListener("click", () => {
    historial = [];
    guardar();
    mensajes.replaceChildren();
    saludar();
    texto.focus();
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = texto.value;
    texto.value = "";
    preguntar(t);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !chat.hidden) cerrar(); });

})();
