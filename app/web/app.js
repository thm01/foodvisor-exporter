(() => {
  const $ = id => document.getElementById(id);
  let csrf, catalog, state, stopped = false, folderTarget = null, refreshTimer;
  let previousConnected = false;
  let countryCodes = [], countryLanguage = null;

  function t(key) {
    return catalog?.[state?.language || 'fr']?.[key] || key;
  }
  function notice(message) {
    $('notice').textContent = message || '';
    $('notice').hidden = !message;
  }
  function countryValue() {
    return $('country-choice').value === '__other__'
      ? $('country').value.trim().toUpperCase() : $('country-choice').value;
  }
  function setCountry(value) {
    const country = (value || '').toUpperCase();
    $('country-choice').value = countryCodes.includes(country) ? country : country ? '__other__' : '';
    $('country').hidden = $('country-choice').value !== '__other__';
    $('country').value = $('country').hidden ? '' : country;
  }
  function renderCountryChoices() {
    if (countryLanguage === state.language) return;
    const previous = countryValue();
    const wasOther = $('country-choice').value === '__other__';
    countryLanguage = state.language;
    const names = catalog[state.language].country_names;
    const items = [['', t('country_choose')],
      ...countryCodes.map(code => [code, `${names[code]} (${code})`]),
      ['__other__', t('country_other')]];
    $('country-choice').replaceChildren(...items.map(([value, label]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      return option;
    }));
    setCountry(previous);
    if (wasOther && !previous) {
      $('country-choice').value = '__other__';
      $('country').hidden = false;
    }
  }
  function translate() {
    document.documentElement.lang = state.language;
    document.title = t('title');
    $('menu-toggle').setAttribute('aria-label', t('menu'));
    $('menu-toggle').title = t('menu');
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
    $('remember-label').textContent = t(state.keyring_available ? 'remember_password' : 'remember_unavailable');
    $('country').placeholder = t('country_custom');
    $('country').setAttribute('aria-label', t('country_custom'));
    $('start-picker').setAttribute('aria-label', t('start'));
    $('end-picker').setAttribute('aria-label', t('end'));
  }
  function render(next, initial = false) {
    const wasConnected = previousConnected;
    state = next;
    previousConnected = state.connected;
    renderCountryChoices();
    if (initial) {
      $('language').value = state.language;
      $('email').value = state.email;
      $('remember').checked = state.remember;
      setCountry(state.country);
      $('data-locale').value = state.data_locale;
      $('destination').value = state.destination;
      $('start').value = state.start;
      $('end').value = state.end;
      syncPicker('start'); syncPicker('end');
    } else if (!wasConnected && state.connected) {
      setCountry(state.country);
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
    ['country-choice', 'country', 'data-locale', 'destination', 'source'].forEach(id => { $(id).disabled = busy; });
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
    if (method === 'GET' && csrf) options.headers = {'X-CSRF-Token': csrf};
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
      scheduleRefresh();
    } catch (error) {
      notice(error.message);
    }
  }
  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    if (!stopped) refreshTimer = setTimeout(refresh, state?.busy || state?.authenticating ? 1000 : 30000);
  }
  async function refresh() {
    if (stopped) return;
    try {
      render(await request('/api/state', null, 'GET'));
    } catch (_) {
      notice(t('server_stopped'));
      stopped = true;
    }
    scheduleRefresh();
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
    try { render(await request('/api/settings', payload)); scheduleRefresh(); }
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
      countryCodes = bootstrap.countries;
      render(await request('/api/state', null, 'GET'), true);
      scheduleRefresh();
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) scheduleRefresh();
        else { clearTimeout(refreshTimer); refresh(); }
      });
    } catch (_) { notice('Local application unavailable. / Application locale indisponible.'); return; }
    $('language').onchange = () => settings({language: $('language').value});
    document.addEventListener('click', event => {
      if (!$('app-menu').contains(event.target)) $('app-menu').open = false;
    });
    $('app-menu').addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        $('app-menu').open = false;
        $('menu-toggle').focus();
      }
    });
    $('email').onchange = () => settings({email: $('email').value});
    $('remember').onchange = () => {
      if ($('remember').checked) settings({remember: true});
      else action('/api/forget');
    };
    $('country-choice').onchange = () => {
      const choice = $('country-choice').value;
      $('country').hidden = choice !== '__other__';
      if (choice === '__other__') {
        $('country').value = '';
        $('country').focus();
      }
      else settings({country: choice});
    };
    $('country').onchange = () => settings({country: countryValue()});
    $('data-locale').onchange = () => settings({data_locale: $('data-locale').value});
    $('destination').onchange = () => settings({destination: $('destination').value});
    $('login').onclick = async () => {
      const password = $('password').value;
      $('password').value = '';
      await action('/api/login', {email: $('email').value, password, remember: $('remember').checked,
                                  country: countryValue(), data_locale: $('data-locale').value});
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
      country: countryValue(), data_locale: $('data-locale').value, destination: $('destination').value});
    $('convert').onclick = () => action('/api/convert', {source: $('source').value,
      country: countryValue(), data_locale: $('data-locale').value, destination: $('destination').value});
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
