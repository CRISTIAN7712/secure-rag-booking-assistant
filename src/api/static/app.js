const chat = document.querySelector("#chat");
const form = document.querySelector("#form");
const input = document.querySelector("#input");
const button = form.querySelector("button");
let history = [];

function addMessage(text, kind, sources = []) {
  const message = document.createElement("div");
  message.className = `msg ${kind}`;
  message.textContent = text;

  if (sources.length) {
    const sourceBox = document.createElement("div");
    sourceBox.className = "sources";
    sourceBox.textContent = "Fuentes recuperadas";

    for (const source of sources) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      const excerpt = document.createElement("p");
      const name = source.metadata.original_filename || source.metadata.source || source.document_id;
      summary.textContent = `[${source.number}] ${name} · ${(source.score * 100).toFixed(1)}%`;
      excerpt.textContent = source.text;
      details.append(summary, excerpt);
      sourceBox.append(details);
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
  const waitingMessage = addMessage("Consultando documentos…", "assistant");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMessage, history }),
    });
    const data = await response.json();
    waitingMessage.remove();
    if (!response.ok) throw new Error(data.detail || "Error del servidor");
    addMessage(data.answer, "assistant", data.sources);
    history.push(
      { role: "user", content: userMessage },
      { role: "assistant", content: data.answer },
    );
    history = history.slice(-12);
  } catch (error) {
    waitingMessage.textContent = `Error: ${error.message}`;
  } finally {
    button.disabled = false;
    input.focus();
  }
});
