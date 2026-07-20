const API_URL = "http://127.0.0.1:8000";
const chat = document.querySelector("#chat");
const form = document.querySelector("#form");
const input = document.querySelector("#input");
const button = form.querySelector("button");
const status = document.querySelector("#status");
const bookingForm = document.querySelector("#booking-form");
const serviceSelect = document.querySelector("#service");
const dateInput = document.querySelector("#appointment-date");
const slotSelect = document.querySelector("#slot");
const bookingResult = document.querySelector("#booking-result");
let history = [];
const chatSessionId = localStorage.getItem("rag_chat_session") || crypto.randomUUID();
localStorage.setItem("rag_chat_session", chatSessionId);

async function checkBackend() {
  try {
    const response = await fetch(`${API_URL}/health`);
    if (!response.ok) throw new Error();
    status.textContent = "Backend conectado";
    status.className = "status online";
  } catch {
    status.textContent = "Backend desconectado: inicia FastAPI en el puerto 8000";
    status.className = "status offline";
  }
}

function addMessage(text, kind, sources = []) {
  const message = document.createElement("div");
  message.className = `msg ${kind}`;
  message.textContent = text;
  if (sources.length) {
    const sourceBox = document.createElement("div");
    sourceBox.className = "sources";
    sourceBox.textContent = "Fuentes recuperadas";
    for (const source of sources) {
      const reference = document.createElement("div");
      const name = source.metadata.original_filename || source.metadata.source || source.document_id;
      reference.textContent = `[${source.number}] ${name} · coincidencia ${(source.score * 100).toFixed(1)}%`;
      sourceBox.append(reference);
    }
    message.append(sourceBox);
  }
  chat.append(message);
  chat.scrollTop = chat.scrollHeight;
  return message;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userMessage = input.value.trim();
  if (!userMessage) return;
  addMessage(userMessage, "user");
  input.value = "";
  button.disabled = true;
  const waiting = addMessage("Consultando documentos…", "assistant");
  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMessage, history, session_id: chatSessionId }),
    });
    const rawBody = await response.text();
    let data = {};
    if (rawBody) {
      try {
        data = JSON.parse(rawBody);
      } catch {
        throw new Error(`El backend devolvió una respuesta no válida (HTTP ${response.status})`);
      }
    }
    if (!response.ok) throw new Error(data.detail || `Error del servidor (HTTP ${response.status})`);
    if (!data.answer) throw new Error("El backend respondió sin contenido");
    waiting.remove();
    addMessage(data.answer, "assistant", data.sources);
    history.push({ role: "user", content: userMessage }, { role: "assistant", content: data.answer });
    history = history.slice(-12);
  } catch (error) {
    waiting.textContent = `Error: ${error.message}`;
  } finally {
    button.disabled = false;
    input.focus();
    checkBackend();
  }
});

checkBackend();

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body?.detail || `Error HTTP ${response.status}`);
  return body;
}

async function loadServices() {
  try {
    const services = await apiRequest("/appointments/services");
    serviceSelect.innerHTML = '<option value="">Selecciona un servicio</option>';
    for (const service of services) {
      const option = document.createElement("option");
      option.value = service.id;
      option.textContent = `${service.name} (${service.duration_minutes} min)`;
      serviceSelect.append(option);
    }
  } catch (error) {
    serviceSelect.innerHTML = '<option value="">Backend no disponible</option>';
  }
}

async function loadSlots() {
  const serviceId = serviceSelect.value;
  const selectedDate = dateInput.value;
  if (!serviceId || !selectedDate) return;
  slotSelect.innerHTML = '<option value="">Consultando…</option>';
  try {
    const slots = await apiRequest(`/appointments/availability?service_id=${encodeURIComponent(serviceId)}&selected_date=${selectedDate}`);
    slotSelect.innerHTML = slots.length ? '<option value="">Selecciona un horario</option>' : '<option value="">No hay horarios disponibles</option>';
    for (const slot of slots) {
      const option = document.createElement("option");
      option.value = slot.id;
      option.textContent = `${new Date(slot.starts_at).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })} · ${slot.professional_name}`;
      slotSelect.append(option);
    }
  } catch (error) {
    slotSelect.innerHTML = '<option value="">Error consultando horarios</option>';
  }
}

const today = new Date();
const localToday = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
dateInput.min = localToday;
dateInput.value = localToday;
serviceSelect.addEventListener("change", loadSlots);
dateInput.addEventListener("change", loadSlots);

bookingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = bookingForm.querySelector("button");
  submit.disabled = true;
  bookingResult.className = "";
  bookingResult.textContent = "Reservando…";
  try {
    const appointment = await apiRequest("/appointments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slot_id: slotSelect.value,
        customer_name: document.querySelector("#customer-name").value,
        customer_email: document.querySelector("#customer-email").value,
        notes: document.querySelector("#notes").value,
      }),
    });
    const when = new Date(appointment.starts_at).toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" });
    bookingResult.className = "success";
    bookingResult.textContent = `Cita confirmada: ${appointment.service_name}, ${when}, con ${appointment.professional_name}. Código: ${appointment.id}`;
    await loadSlots();
  } catch (error) {
    bookingResult.className = "error";
    bookingResult.textContent = `No se pudo reservar: ${error.message}`;
  } finally {
    submit.disabled = false;
  }
});

loadServices();
