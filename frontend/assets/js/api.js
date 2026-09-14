/**
 * BhashaSetu — centralized frontend API layer.
 *
 * Every screen talks to the Flask backend through these helpers.
 * - Auth token is read from localStorage (set by the login screen).
 * - All /api calls are sent to the same origin (Flask also serves the Stitch
 *   pages), so no CORS configuration is needed. For a dev setup where the
 *   frontend is served on a different port, override with:
 *     window.BHASHASETU_API_BASE = "http://localhost:5000"
 *   BEFORE this script runs.
 */
(function () {
  'use strict';

  function baseUrl() {
    if (window.BHASHASETU_API_BASE) return window.BHASHASETU_API_BASE.replace(/\/+$/, '');
    return '';
  }

  var TOKEN_KEY = 'bhashasetu_token';
  var TEACHER_KEY = 'bhashasetu_teacher';

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  function getTeacher() {
    try {
      return JSON.parse(localStorage.getItem(TEACHER_KEY) || 'null');
    } catch (e) {
      return null;
    }
  }

  function setSession(token, teacher) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (teacher) localStorage.setItem(TEACHER_KEY, JSON.stringify(teacher));
  }

  function isLoggedIn() {
    return !!getToken();
  }

  function authHeaders(headers) {
    var out = headers || {};
    var token = getToken();
    if (token && !out['Authorization']) out['Authorization'] = 'Bearer ' + token;
    return out;
  }

  /**
   * Core fetch wrapper.
   * options: { method, body (object|FormData), headers, params, raw }
   * - raw: true -> return the Response so callers can handle non-2xx themselves.
   */
  function request(path, options) {
    options = options || {};
    var url = baseUrl() + path;

    var params = options.params;
    if (params) {
      var qs = new URLSearchParams();
      Object.keys(params).forEach(function (k) {
        var v = params[k];
        if (v !== undefined && v !== null && v !== '') qs.set(k, v);
      });
      var q = qs.toString();
      if (q) url += (url.indexOf('?') === -1 ? '?' : '&') + q;
    }

    var headers = authHeaders(options.headers || {});
    var body = options.body;

    if (body !== undefined && body !== null && !(body instanceof FormData)) {
      if (typeof body !== 'string') {
        body = JSON.stringify(body);
      }
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    return fetch(url, {
      method: options.method || 'GET',
      headers: headers,
      body: body,
    }).then(function (resp) {
      if (options.raw) return resp;

      return resp
        .json()
        .catch(function () {
          return {};
        })
        .then(function (payload) {
          if (resp.status === 401) {
            sessionStorage.setItem('bhashasetu_redirect', window.location.pathname + window.location.search);
            window.location.href = '/';
            var err = new Error(payload.message || payload.error || 'Login required.');
            err.status = resp.status;
            throw err;
          }
          if (!resp.ok) {
            var msg = payload.message || payload.error || 'Request failed (' + resp.status + ')';
            var e = new Error(msg);
            e.status = resp.status;
            e.payload = payload;
            throw e;
          }
          return payload;
        });
    });
  }

  function get(path, params) {
    return request(path, { params: params });
  }

  function post(path, body, extra) {
    extra = extra || {};
    return request(path, {
      method: 'POST',
      body: body,
      headers: extra.headers,
      params: extra.params,
      raw: extra.raw,
    });
  }

  // ---- Convenience wrappers used by the screens -------------------------
  function translate(text, sourceLanguage, targetLanguage) {
    return post('/api/translate', {
      text: text,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    });
  }

  function transcribe(payload) {
    return post('/api/speech/transcribe', payload || { demo_key: 'teacher_default', expected_language: 'hi' });
  }

  function submitDoubt(payload) {
    return post('/api/doubt', payload || { demo_key: 'student_doubt' });
  }

  function analytics(worksheetId, classSize) {
    return get('/api/analytics', {
      worksheet_id: worksheetId,
      class_size: classSize,
    });
  }

  /**
   * Honest AI-status label for any backend response that carries a mode/engine
   * pair (e.g. doubt.explanation, worksheet generation, misconception analysis).
   * Never claims a live LLM when the backend labelled the result as a fallback.
   */
  function getAIStatusLabel(source) {
    var mode = source && typeof source === 'object' ? source.mode : source;
    var engine = source && typeof source === 'object' ? source.engine : '';
    mode = String(mode == null ? '' : mode).toLowerCase();
    engine = String(engine == null ? '' : engine);
    var model = 'AI';
    if (engine.indexOf('qwen') !== -1) model = 'Qwen 2.5';
    else if (engine === 'nllb-200') model = 'NLLB-200';
    else if (engine === 'bhashini') model = 'Bhashini MT';
    if (mode === 'real') return { text: model + ' • Real', status: 'real' };
    if (mode === 'demo') return { text: 'Demo AI', status: 'fallback' };
    return { text: 'AI Fallback', status: 'fallback' };
  }

  function dictionary(query, sourceLanguage, targetLanguage) {
    var params = {};
    if (query) params.query = query;
    if (sourceLanguage) params.source = sourceLanguage;
    if (targetLanguage) params.target = targetLanguage;
    return get('/api/dictionary', Object.keys(params).length ? params : undefined);
  }

  window.BhashaSetuAPI = {
    request: request,
    get: get,
    post: post,
    translate: translate,
    transcribe: transcribe,
    submitDoubt: submitDoubt,
    analytics: analytics,
    getAIStatusLabel: getAIStatusLabel,
    dictionary: dictionary,
    getToken: getToken,
    getTeacher: getTeacher,
    setSession: setSession,
    isLoggedIn: isLoggedIn,
  };
})();