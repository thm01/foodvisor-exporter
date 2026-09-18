(() => {
  const $ = id => document.getElementById(id);
  let csrf, catalog, state, stopped = false, folderTarget = null;
  let previousConnected = false;
  const fields = ['email', 'password', 'country', 'data-locale', 'destination', 'start', 'end', 'source'];

  function t(key) {
    return catalog?.[state?.language || 'fr']?.[key] || key;
  }
  function notice(message) {
    $('notice').textContent = message || '';
    $('notice').hidden = !message;
  }
  function translate() {
    document.documentElement.lang = state.language;
    document.title = t('title');
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
    $('remember-label').textContent = t(state.keyring_available ? 'remember_password' : 'remember_unavailable');
    $('start-picker').setAttribute('aria-label', t('start'));
    $('end-picker').setAttribute('aria-label', t('end'));
  }
  function render(next, initial = false) {
    const wasConnected = previousConnected;
    state = next;
    previousConnected = state.connected;
    if (initial) {
      $('language').value = state.language;
      $('email').value = state.email;
      $('remember').checked = state.remember;
      $('country').value = state.country;
      $('data-locale').value = state.data_locale;
      $('destination').value = state.destination;
      $('start').value = state.start;
      $('end').value = state.end;
      syncPicker('start'); syncPicker('end');
    } else if (!wasConnected && state.connected) {
      $('country').value = state.country;
      $('data-locale').value = state.data_locale;
      $('password').value = '';
    }
    $('language').value = state.language;
    $('remember').checked = state.remember;
    translate();
    const busy = state.busy || state.authenticating;
    $('account-status').textContent = t(state.authenticating ? 'connecting' : state.connected ? 'connected' : 'disconnected');
    $('status').textContent = state.error ? `${t('error')}: ${state.error}` : t(state.status);
    $('progress-bar').hidden = !busy;
    $('login').disabled = busy || state.connected;
    $('logout').disabled = busy || !state.connected;
    $('forget').disabled = busy || !state.remembered_email;
    $('email').disabled = busy || state.connected;
    $('password').disabled = busy || state.connected;
    $('remember').disabled = busy || state.connected || !state.keyring_available;
    ['start', 'end', 'start-picker', 'end-picker'].forEach(id => { $(id).disabled = busy || !state.connected; });
    ['country', 'data-locale', 'destination', 'source'].forEach(id => { $(id).disabled = busy; });
    $('browse-destination').disabled = busy;
    $('browse-source').disabled = busy;
    $('export').disabled = busy || !state.connected;
    $('convert').disabled = busy;
    $('cancel').disabled = !state.busy;
    $('open-output').disabled = !state.last_output;
    const logText = state.messages.join('\n');
    if ($('log').textContent !== logText) {
      $('log').textContent = logText;
      $('log').scrollTop = $('log').scrollHeight;
    }
  }
  async function request(path, payload, method = 'POST') {
    const options = {method, cache: 'no-store'};
    if (method === 'POST') {
      options.headers = {'Content-Type': 'application/json', 'X-CSRF-Token': csrf};
      options.body = JSON.stringify(payload || {});
    }
    const response = await fetch(path, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `${response.status}`);
    return body;
  }
  async function action(path, payload = {}) {
    notice('');
    try {
      render(await request(path, payload));
    } catch (error) {
      notice(error.message);
    }
  }
  async function refresh() {
    if (stopped) return;
    try {
      render(await request('/api/state', null, 'GET'));
    } catch (_) {
      notice(t('server_stopped'));
      stopped = true;
    }
  }
  function isoFromText(value) {
    const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value.trim());
    if (!match) return '';
    const iso = `${match[3]}-${match[2]}-${match[1]}`;
    const date = new Date(`${iso}T12:00:00`);
    return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === iso ? iso : '';
  }
  function syncPicker(id) {
    $(id + '-picker').value = isoFromText($(id).value);
  }
  function syncText(id) {
    const value = $(id + '-picker').value;
    if (value) {
      const [year, month, day] = value.split('-');
      $(id).value = `${day}-${month}-${year}`;
    }
  }
  async function settings(payload) {
    try { render(await request('/api/settings', payload)); }
    catch (error) { notice(error.message); }
  }
  async function showFolder(target) {
    folderTarget = target;
    $('folder-title').textContent = t(target === 'source' ? 'source' : 'destination');
    $('folder-dialog').showModal();
    await listFolder($(target).value || state.destination);
  }
  async function listFolder(path) {
    try {
      const result = await request('/api/directories?path=' + encodeURIComponent(path), null, 'GET');
      $('folder-path').value = result.path;
      $('folder-list').replaceChildren();
      $('parent-folder').onclick = () => listFolder(result.parent);
      for (const name of result.children) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `📁  ${name}`;
        button.onclick = () => listFolder(result.path.replace(/[\\/]$/, '') + (result.path.includes('\\') ? '\\' : '/') + name);
        $('folder-list').append(button);
      }
      if (!result.children.length) $('folder-list').textContent = t('folder_empty');
    } catch (error) { notice(error.message); }
  }
  async function init() {
    try {
      const bootstrap = await request('/api/i18n', null, 'GET');
      csrf = bootstrap.csrf;
      catalog = bootstrap.ui;
      bootstrap.countries.forEach(code => { const option = document.createElement('option'); option.value = code; $('countries').append(option); });
      render(await request('/api/state', null, 'GET'), true);
      setInterval(refresh, 700);
    } catch (_) { notice('Local application unavailable. / Application locale indisponible.'); return; }
    $('language').onchange = () => settings({language: $('language').value});
    $('email').onchange = () => settings({email: $('email').value});
    $('remember').onchange = () => {
      if ($('remember').checked) settings({remember: true});
      else action('/api/forget');
    };
    $('country').onchange = () => settings({country: $('country').value, data_locale: $('data-locale').value});
    $('data-locale').onchange = () => settings({country: $('country').value, data_locale: $('data-locale').value});
    $('destination').onchange = () => settings({destination: $('destination').value});
    $('login').onclick = async () => {
      const password = $('password').value;
      $('password').value = '';
      await action('/api/login', {email: $('email').value, password, remember: $('remember').checked,
                                  country: $('country').value, data_locale: $('data-locale').value});
    };
    $('logout').onclick = () => action('/api/logout');
    $('forget').onclick = () => action('/api/forget');
    for (const id of ['start', 'end']) {
      $(id).onchange = () => syncPicker(id);
      $(id + '-picker').onchange = () => syncText(id);
    }
    $('browse-destination').onclick = () => showFolder('destination');
    $('browse-source').onclick = () => showFolder('source');
    $('export').onclick = () => action('/api/export', {start: $('start').value, end: $('end').value,
      country: $('country').value, data_locale: $('data-locale').value, destination: $('destination').value});
    $('convert').onclick = () => action('/api/convert', {source: $('source').value,
      country: $('country').value, data_locale: $('data-locale').value, destination: $('destination').value});
    $('cancel').onclick = () => action('/api/cancel');
    $('open-output').onclick = () => action('/api/open');
    $('copy-log').onclick = async () => { try { await navigator.clipboard.writeText($('log').textContent); } catch (error) { notice(error.message); } };
    $('clear-log').onclick = () => action('/api/clear');
    $('close-dialog').onclick = () => $('folder-dialog').close();
    $('go-folder').onclick = () => listFolder($('folder-path').value);
    $('folder-path').onkeydown = event => { if (event.key === 'Enter') listFolder($('folder-path').value); };
    $('choose-folder').onclick = () => {
      $(folderTarget).value = $('folder-path').value;
      $('folder-dialog').close();
      if (folderTarget === 'destination') settings({destination: $('destination').value});
    };
    $('quit').onclick = async () => {
      if (!confirm(t('quit_confirm'))) return;
      stopped = true;
      await action('/api/quit');
      notice(t('server_stopped'));
    };
  }
  document.addEventListener('DOMContentLoaded', init);
})();
