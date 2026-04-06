function toggleFeedback() {
  const drawer = document.getElementById("feedbackDrawer");
  if (!drawer) return;
  drawer.style.display = drawer.style.display === "block" ? "none" : "block";
}

function saveFeedback() {
  const note = document.getElementById("feedbackNote");
  if (!note) return;
  alert("Feedback captured:\n\n" + note.value);
  note.value = "";
  toggleFeedback();
}
