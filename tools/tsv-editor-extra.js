'use strict';

const generateButton = document.createElement('button');
generateButton.id = 'generate';
generateButton.textContent = 'Generate Patch';
document.getElementById('apply').after(generateButton);

generateButton.addEventListener('click', async () => {
  if (location.protocol === 'file:') {
    alert('Generate Patch requires run-tsv-editor.sh.');
    return;
  }
  const dialog = document.getElementById('buildDialog');
  const state = document.getElementById('buildState');
  const log = document.getElementById('buildLog');
  dialog.showModal();
  state.textContent = 'Starting xdelta generation…';
  log.textContent = '';
  generateButton.disabled = true;
  try {
    const response = await fetch('/api/generate-patch', {method: 'POST'});
    if (!response.ok) throw new Error(await response.text());
    pollPatchStatus();
  } catch (error) {
    state.textContent = 'Could not generate patch';
    log.textContent = error.message;
    generateButton.disabled = false;
  }
});

async function pollPatchStatus() {
  const state = document.getElementById('buildState');
  const log = document.getElementById('buildLog');
  try {
    const status = await (await fetch('/api/status')).json();
    state.textContent = status.state + (status.output ? ` · ${status.output}` : '');
    log.textContent = status.log;
    log.scrollTop = log.scrollHeight;
    if (status.state === 'running') setTimeout(pollPatchStatus, 750);
    else generateButton.disabled = false;
  } catch (error) {
    state.textContent = 'Status error';
    log.textContent += error.message;
    generateButton.disabled = false;
  }
}
