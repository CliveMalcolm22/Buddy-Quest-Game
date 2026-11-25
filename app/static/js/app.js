document.addEventListener('click', (event) => {
  const closeButton = event.target.closest('.close-button');
  if (!closeButton) return;

  const modal = document.querySelector('.modal-backdrop');
  if (modal) modal.remove();
});

document.addEventListener('click', (event) => {
  const backdrop = event.target.closest('.modal-backdrop');
  if (backdrop && event.target === backdrop) backdrop.remove();
});

document.body.addEventListener('taskSaved', () => {
  document.querySelector('.modal-backdrop')?.remove();
});

document.body.addEventListener('taskChanged', () => {
  const summary = document.querySelector('#summary-row');
  if (summary) htmx.ajax('GET', '/summary', { target: summary, swap: 'innerHTML' });
  const taskList = document.querySelector('#task-list');
  if (taskList && !taskList.querySelector('.task-card') && !taskList.querySelector('#empty-tasks')) {
    htmx.ajax('GET', '/tasks/empty', { target: '#task-list', swap: 'innerHTML' });
  }
});

document.body.addEventListener('htmx:beforeSwap', (event) => {
  if (event.detail.xhr.status === 422 || event.detail.xhr.status === 409 || event.detail.xhr.status === 404) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});
document.getElementById("friend-search-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = document.getElementById("friend-search").value.trim();
  const results = document.getElementById("friend-search-results");

  if (query.length < 2) {
    results.textContent = "Enter at least 2 characters.";
    return;
  }

  const response = await fetch(`/friends/search?q=${encodeURIComponent(query)}`);
  const users = await response.json();

  results.innerHTML = "";

  users.forEach(user => {
    const item = document.createElement("div");
    item.innerHTML = `
      <span>${user.display_name || user.username} (@${user.username})</span>
      <button type="button" data-friend-id="${user.friend_id}">Send Request</button>
    `;
    results.appendChild(item);
  });

  if (users.length === 0) results.textContent = "No users found.";
});

document.getElementById("friend-search-results")?.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-friend-id]");
  if (!button) return;

  const response = await fetch("/friends/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ friend_id: Number(button.dataset.friendId) })
  });

  const result = await response.json();
  alert(response.ok ? "Friend request sent!" : result.detail || "Could not send request.");
  if (response.ok) button.disabled = true;
});
document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", async () => {
    const id = button.dataset.id;
    const action = button.dataset.action;

    const response = await fetch(`/friends/requests/${id}/${action}`, {
      method: "POST"
    });

    if (response.ok) {
      alert("Friend request updated.");
      location.reload();
    } else {
      alert("Something went wrong.");
    }
  });
});