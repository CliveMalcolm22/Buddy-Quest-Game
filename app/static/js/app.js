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
