/* Night Ferry player — dependency-free, no network.
 *
 * Loads ../case/truth-sheet.json plus the two scene files named there when the
 * page is served over http(s). Under file:// browsers refuse sibling JSON
 * fetches, so the page falls back to the labelled bundled fixture, or to JSON
 * files the reader loads by hand. Nothing leaves this page.
 */
(function () {
  'use strict';

  var FACT_IDS = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6'];
  var SCENE_IDS = ['landing-clerk', 'engine-room'];

  var state = {
    truth: null,
    scenes: new Map(),      // id -> validated scene object
    source: '',
    route: [],
    evidence: new Set(),    // "sceneId#index"
    activeScene: null,
    submitted: false,
    submittedText: '',
    submittedAt: null,
    answerRevealed: false,
    selfCheck: '',
    fixture: false
  };

  function $(id) { return document.getElementById(id); }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function log(text) {
    state.route.push({ at: new Date(), text: text });
    renderRoute();
  }

  function nowLabel(date) {
    try {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (err) {
      return '';
    }
  }

  function fail(message) {
    throw new Error(message);
  }

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function nonEmpty(value, what) {
    if (typeof value !== 'string' || !value.trim()) fail(what + ' must be a non-empty string');
    return value.trim();
  }

  /* ---------- validation ---------- */

  function validateTruth(value) {
    if (!isObject(value)) fail('truth sheet must be a JSON object');
    nonEmpty(value.case, 'truth-sheet "case"');
    nonEmpty(value.title, 'truth-sheet "title"');
    if (!Array.isArray(value.facts) || value.facts.length !== 6) {
      fail('truth sheet needs exactly six facts');
    }
    var seenFacts = new Set();
    value.facts.forEach(function (fact, index) {
      if (!isObject(fact)) fail('fact ' + (index + 1) + ' must be an object');
      var id = nonEmpty(fact.id, 'fact ' + (index + 1) + ' id');
      if (FACT_IDS.indexOf(id) === -1) fail('fact id must be F1–F6, got "' + id + '"');
      if (seenFacts.has(id)) fail('duplicate fact id ' + id);
      seenFacts.add(id);
      nonEmpty(fact.statement, 'fact ' + id + ' statement');
    });
    FACT_IDS.forEach(function (id) {
      if (!seenFacts.has(id)) fail('missing fact ' + id);
    });
    if (!isObject(value.deduction)) fail('truth sheet needs a deduction object');
    nonEmpty(value.deduction.question, 'deduction question');
    nonEmpty(value.deduction.answer, 'deduction answer');
    if (!Array.isArray(value.scenes) || value.scenes.length !== 2) {
      fail('truth sheet needs exactly two scenes');
    }
    var seenScenes = new Set();
    value.scenes.forEach(function (scene, index) {
      if (!isObject(scene)) fail('scene entry ' + (index + 1) + ' must be an object');
      var id = nonEmpty(scene.id, 'scene ' + (index + 1) + ' id');
      if (SCENE_IDS.indexOf(id) === -1) fail('scene id must be landing-clerk or engine-room, got "' + id + '"');
      if (seenScenes.has(id)) fail('duplicate scene id ' + id);
      seenScenes.add(id);
      nonEmpty(scene.file, 'scene ' + id + ' file');
      nonEmpty(scene.title, 'scene ' + id + ' title');
    });
    SCENE_IDS.forEach(function (id) {
      if (!seenScenes.has(id)) fail('missing scene ' + id);
    });
    return value;
  }

  function validateScene(value, truth) {
    if (!isObject(value)) fail('scene must be a JSON object');
    var id = nonEmpty(value.id, 'scene "id"');
    if (SCENE_IDS.indexOf(id) === -1) fail('unknown scene id "' + id + '"');
    nonEmpty(value.title, 'scene ' + id + ' title');
    nonEmpty(value.perspective, 'scene ' + id + ' perspective');
    if (!Array.isArray(value.paragraphs) || value.paragraphs.length === 0) {
      fail('scene ' + id + ' needs at least one paragraph');
    }
    value.paragraphs.forEach(function (paragraph, index) {
      nonEmpty(paragraph, 'scene ' + id + ' paragraph ' + (index + 1));
    });
    if (!Array.isArray(value.statements)) fail('scene ' + id + ' needs a statements array');
    var known = new Set(truth.facts.map(function (fact) { return fact.id; }));
    value.statements.forEach(function (statement, index) {
      if (!isObject(statement)) fail('scene ' + id + ' statement ' + (index + 1) + ' must be an object');
      if (!known.has(statement.fact)) {
        fail('scene ' + id + ' statement ' + (index + 1) + ' cites unknown fact "' + statement.fact + '"');
      }
      nonEmpty(statement.text, 'scene ' + id + ' statement ' + (index + 1) + ' text');
    });
    return value;
  }

  function validateCase(truthValue, sceneValues) {
    var truth = validateTruth(truthValue);
    var byId = new Map();
    sceneValues.forEach(function (sceneValue) {
      var scene = validateScene(sceneValue, truth);
      if (byId.has(scene.id)) fail('duplicate scene file for ' + scene.id);
      byId.set(scene.id, scene);
    });
    SCENE_IDS.forEach(function (id) {
      if (!byId.has(id)) fail('no scene file loaded for ' + id);
    });
    return { truth: truth, scenes: byId };
  }

  /* ---------- loading ---------- */

  function setCase(truth, sceneValues, source, options) {
    var parsed;
    try {
      parsed = validateCase(truth, sceneValues);
    } catch (err) {
      setLoadStatus('Could not load: ' + err.message, true);
      return false;
    }
    state.truth = parsed.truth;
    state.scenes = parsed.scenes;
    state.source = source;
    state.fixture = !!(options && options.fixture);
    state.route = [];
    state.evidence = new Set();
    state.activeScene = null;
    state.submitted = false;
    state.submittedText = '';
    state.submittedAt = null;
    state.answerRevealed = false;
    state.selfCheck = '';

    $('case-title').textContent = state.truth.title;
    $('case-question').textContent = state.truth.deduction.question;
    $('case-question').hidden = false;
    $('case-kicker').textContent = state.fixture ? 'Fixture check · not the real case' : 'Emberhall case';
    $('case-sub').textContent = state.fixture
      ? 'Placeholder text only. It proves the page loads, separates accounts, gates the answer and exports a record.'
      : 'Read both accounts, mark what you rely on, then submit your own explanation.';
    $('source-note').textContent = 'Loaded from ' + source + '.';
    var badge = $('mode-badge');
    badge.hidden = !state.fixture;
    badge.textContent = state.fixture ? 'fixture — not story content' : '';

    $('answer-panel').hidden = true;
    $('answer-question').textContent = '';
    $('answer-text').textContent = '';
    $('record-text').hidden = true;
    $('record-text').value = '';
    $('cited-summary').textContent = '';
    $('explanation').value = '';
    $('explanation').disabled = false;
    $('submit').disabled = false;
    document.querySelectorAll('input[name="selfcheck"]').forEach(function (input) { input.checked = false; });
    $('load-status').textContent = '';
    $('export-status').textContent = '';

    renderTabs();
    renderNotebook();
    renderScene(null);
    log('loaded ' + source);
    return true;
  }

  function useFixture(reason) {
    var fixture = window.NIGHT_FERRY_FIXTURE;
    if (!fixture || !fixture.truth || !fixture.scenes) {
      setLoadStatus('No bundled fixture is available on this page.', true);
      return;
    }
    var scenes = SCENE_IDS.map(function (id) { return fixture.scenes[id]; });
    if (setCase(fixture.truth, scenes, 'bundled fixture (placeholder text)', { fixture: true })) {
      if (reason) setLoadStatus(reason, false);
    }
  }

  function fetchJSON(url) {
    return fetch(url, { cache: 'no-store' }).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    });
  }

  function boot() {
    var params = new URLSearchParams(window.location.search);
    if (params.get('fixture') === '1') {
      useFixture('Showing the bundled fixture because the page was opened with ?fixture=1.');
      return;
    }
    if (window.location.protocol === 'file:') {
      // Browsers block file:// fetches of sibling JSON; do not pretend otherwise.
      var reason = 'Opened from file://, where browsers block reading ../case/. Showing the bundled fixture instead; load the real files with “Load case files…”, or serve the folder over http.';
      if (window.NIGHT_FERRY_FIXTURE) useFixture(reason);
      else showLoader('No bundled fixture is available. Use “Load case files…” to open truth-sheet.json and both scene files.');
      return;
    }
    var base = new URL('../case/', window.location.href);
    var truthLoaded = false;
    fetchJSON(new URL('truth-sheet.json', base))
      .then(function (truth) {
        truthLoaded = true;
        validateTruth(truth);
        return Promise.all(truth.scenes.map(function (entry) {
          return fetchJSON(new URL(entry.file, base));
        })).then(function (scenes) {
          setCase(truth, scenes, '../case/ (truth sheet and two scene files)', { fixture: false });
        });
      })
      .catch(function (err) {
        var reason = 'Could not read ../case/ (' + (err && err.message ? err.message : err) + ').';
        if (truthLoaded) {
          // Do not hide a broken real case behind the fixture.
          showLoader(reason + ' Fix the case files, or press “Use fixture” to check the page itself.');
          return;
        }
        if (window.NIGHT_FERRY_FIXTURE) {
          useFixture(reason + ' Showing the bundled fixture so the page can still be checked.');
        } else {
          showLoader(reason + ' Use “Load case files…” to choose truth-sheet.json and both scene files.');
        }
      });
  }

  function showLoader(message) {
    $('load-fixture').hidden = !window.NIGHT_FERRY_FIXTURE;
    setLoadStatus(message, true);
  }

  function setLoadStatus(message, isError) {
    var status = $('load-status');
    status.textContent = message || '';
    status.classList.toggle('error', !!isError);
  }

  /* ---------- manual file loading ---------- */

  function handleFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;
    setLoadStatus('Reading ' + files.length + ' file' + (files.length === 1 ? '' : 's') + '…', false);

    var truthCandidate = null;
    var sceneCandidates = new Map();
    var errors = [];
    var pending = files.length;

    files.forEach(function (file) {
      var reader = new FileReader();
      reader.onerror = function () {
        errors.push(file.name + ': could not be read');
        done();
      };
      reader.onload = function () {
        try {
          var value = JSON.parse(String(reader.result));
          if (isObject(value) && Array.isArray(value.facts) && isObject(value.deduction)) {
            if (truthCandidate) throw new Error('more than one truth sheet selected');
            truthCandidate = value;
          } else if (isObject(value) && typeof value.id === 'string' && Array.isArray(value.statements)) {
            if (sceneCandidates.has(value.id)) throw new Error('two scene files claim id ' + value.id);
            sceneCandidates.set(value.id, value);
          } else {
            throw new Error('not a truth sheet or scene file');
          }
        } catch (err) {
          errors.push(file.name + ': ' + err.message);
        }
        done();
      };
      reader.readAsText(file);
    });

    function done() {
      pending -= 1;
      if (pending > 0) return;
      if (!truthCandidate) {
        setLoadStatus('No truth sheet among those files. ' + errors.join('; '), true);
        return;
      }
      var scenes = [];
      SCENE_IDS.forEach(function (id) {
        if (sceneCandidates.has(id)) scenes.push(sceneCandidates.get(id));
      });
      var missing = SCENE_IDS.filter(function (id) { return !sceneCandidates.has(id); });
      if (missing.length) {
        setLoadStatus('Loaded the truth sheet but still need: ' + missing.join(', ') + '. ' + errors.join('; '), true);
        return;
      }
      if (setCase(truthCandidate, scenes, 'files you chose', { fixture: false })) {
        setLoadStatus('Loaded ' + (files.length) + ' file' + (files.length === 1 ? '' : 's') + ' by hand.' +
          (errors.length ? ' Ignored: ' + errors.join('; ') : ''), false);
      }
    }
  }

  /* ---------- rendering ---------- */

  function renderTabs() {
    var tabs = $('tabs');
    tabs.textContent = '';
    if (!state.truth) { tabs.hidden = true; return; }
    tabs.hidden = false;
    state.truth.scenes.forEach(function (entry) {
      var button = el('button', 'tab', entry.title);
      button.type = 'button';
      button.dataset.scene = entry.id;
      button.setAttribute('aria-pressed', String(state.activeScene === entry.id));
      button.addEventListener('click', function () { openScene(entry.id); });
      tabs.appendChild(button);
    });
  }

  function openScene(id) {
    if (!state.scenes.has(id)) return;
    state.activeScene = id;
    syncTabs();
    renderScene(id);
    var title = state.scenes.get(id).title;
    log('opened ' + id + ' (“' + title + '”)');
  }

  /* Update existing controls in place so the element that received the event
   * keeps keyboard focus. Rebuilding these lists on every tick or tab press
   * would otherwise drop focus to the document body. */
  function syncTabs() {
    document.querySelectorAll('#tabs button.tab').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.scene === state.activeScene));
    });
  }

  function syncEvidenceBoxes() {
    document.querySelectorAll('input[type="checkbox"][data-key]').forEach(function (box) {
      box.checked = state.evidence.has(box.dataset.key);
    });
  }

  function renderScene(id) {
    var panel = $('scene-panel');
    panel.textContent = '';
    if (!id || !state.scenes.has(id)) {
      panel.appendChild(el('p', 'placeholder',
        'Choose an account above to read it. Mark the statements you rely on; the notebook on the right collects them by fact.'));
      return;
    }
    var scene = state.scenes.get(id);
    var head = el('div', 'scene-head');
    head.appendChild(el('p', 'kicker', scene.perspective + ' perspective'));
    head.appendChild(el('h2', '', scene.title));
    panel.appendChild(head);

    var prose = el('div', 'prose');
    scene.paragraphs.forEach(function (paragraph) {
      prose.appendChild(el('p', '', paragraph));
    });
    panel.appendChild(prose);

    var evidenceHead = el('div', 'evidence-head');
    evidenceHead.appendChild(el('h3', '', 'Statements in this account'));
    evidenceHead.appendChild(el('p', 'muted', 'Tick what you use. A fact can appear in both accounts.'));
    panel.appendChild(evidenceHead);
    panel.appendChild(renderStatementList(id));
  }

  function statementKey(sceneId, index) { return sceneId + '#' + index; }

  function renderStatementList(sceneId) {
    var scene = state.scenes.get(sceneId);
    var list = el('ul', 'statements');
    scene.statements.forEach(function (statement, index) {
      var key = statementKey(sceneId, index);
      var item = el('li', 'statement');
      var label = el('label');
      var box = document.createElement('input');
      box.type = 'checkbox';
      box.dataset.key = key;
      box.checked = state.evidence.has(key);
      box.addEventListener('change', function () { toggleEvidence(key, box.checked); });
      label.appendChild(box);
      label.appendChild(el('span', 'fact-chip', statement.fact));
      label.appendChild(el('span', 'statement-text', statement.text));
      item.appendChild(label);
      list.appendChild(item);
    });
    return list;
  }

  function toggleEvidence(key, checked) {
    if (checked) state.evidence.add(key); else state.evidence.delete(key);
    var parts = key.split('#');
    var scene = state.scenes.get(parts[0]);
    var statement = scene && scene.statements[Number(parts[1])];
    if (statement) {
      log((checked ? 'cited ' : 'uncited ') + statement.fact + ' in ' + parts[0]);
    }
    syncEvidenceBoxes();
  }

  function renderNotebook() {
    var notebook = $('notebook');
    notebook.textContent = '';
    if (!state.truth) {
      notebook.appendChild(el('p', 'muted', 'No case loaded yet.'));
      return;
    }
    state.truth.facts.forEach(function (fact) {
      var section = el('section', 'fact-block');
      var heading = el('div', 'fact-head');
      heading.appendChild(el('span', 'fact-chip', fact.id));
      // Deliberately do not render truth-sheet fact.statement: those canonical
      // facts can bypass what either account actually witnesses. The notebook
      // groups only statements the two accounts state.
      section.appendChild(heading);

      var rows = el('ul', 'fact-rows');
      var count = 0;
      SCENE_IDS.forEach(function (sceneId) {
        var scene = state.scenes.get(sceneId);
        if (!scene) return;
        scene.statements.forEach(function (statement, index) {
          if (statement.fact !== fact.id) return;
          count += 1;
          var key = statementKey(sceneId, index);
          var row = el('li', 'fact-row');
          var label = el('label');
          var box = document.createElement('input');
          box.type = 'checkbox';
          box.dataset.key = key;
          box.checked = state.evidence.has(key);
          box.addEventListener('change', function () { toggleEvidence(key, box.checked); });
          label.appendChild(box);
          label.appendChild(el('span', 'scene-tag', sceneId));
          label.appendChild(el('span', 'statement-text', statement.text));
          row.appendChild(label);
          rows.appendChild(row);
        });
      });
      if (!count) rows.appendChild(el('li', 'muted', 'Neither loaded account states this fact directly.'));
      section.appendChild(rows);
      notebook.appendChild(section);
    });
  }

  function renderRoute() {
    var list = $('route');
    list.textContent = '';
    if (!state.route.length) {
      list.appendChild(el('li', 'muted', 'Nothing yet.'));
      return;
    }
    state.route.forEach(function (entry) {
      var item = el('li');
      item.appendChild(el('span', 'route-time', nowLabel(entry.at)));
      item.appendChild(document.createTextNode(entry.text));
      list.appendChild(item);
    });
    list.scrollTop = list.scrollHeight;
  }

  /* ---------- submit and export ---------- */

  function submitExplanation() {
    if (!state.truth) {
      setLoadStatus('Load a case first.', true);
      return;
    }
    if (state.submitted) return;
    var text = $('explanation').value.trim();
    if (!text) {
      $('submit-hint').textContent = 'Write at least a sentence before submitting.';
      $('explanation').focus();
      return;
    }
    state.submitted = true;
    state.submittedText = text;
    state.submittedAt = new Date();
    state.answerRevealed = true;

    $('answer-question').textContent = state.truth.deduction.question;
    $('answer-text').textContent = state.truth.deduction.answer;
    $('answer-note').textContent = 'Answer revealed after submit. Your explanation is kept as written at submit time; this page does not mark prose.';
    $('answer-panel').hidden = false;
    $('submit').disabled = true;
    $('explanation').disabled = true;
    $('submit-hint').textContent = 'Submitted. Export the plain-text record for the integrator.';
    renderCitedSummary();
    log('submitted final explanation');
    log('answer revealed');
    $('export').focus();
  }

  function citedFacts() {
    var cited = new Set();
    state.evidence.forEach(function (key) {
      var parts = key.split('#');
      var scene = state.scenes.get(parts[0]);
      var statement = scene && scene.statements[Number(parts[1])];
      if (statement) cited.add(statement.fact);
    });
    return cited;
  }

  function renderCitedSummary() {
    var cited = citedFacts();
    var missing = FACT_IDS.filter(function (id) { return !cited.has(id); });
    var summary = 'Facts cited: ' + (cited.size ? FACT_IDS.filter(function (id) { return cited.has(id); }).join(', ') : 'none') + '.';
    if (missing.length) summary += ' Not cited: ' + missing.join(', ') + '.';
    $('cited-summary').textContent = summary;
  }

  function buildRecord() {
    var lines = [];
    lines.push('Night Ferry — playtest record');
    lines.push('case: ' + state.truth.case);
    lines.push('title: ' + state.truth.title);
    lines.push('source: ' + state.source);
    lines.push('exported: ' + new Date().toISOString());
    lines.push('submitted: ' + (state.submittedAt ? state.submittedAt.toISOString() : 'not submitted'));
    lines.push('');
    lines.push('ROUTE');
    state.route.forEach(function (entry, index) {
      lines.push(' ' + (index + 1) + '. [' + nowLabel(entry.at) + '] ' + entry.text);
    });
    lines.push('');
    lines.push('EVIDENCE CITED');
    if (!state.evidence.size) {
      lines.push(' (none)');
    } else {
      FACT_IDS.forEach(function (factId) {
        var fact = state.truth.facts.filter(function (item) { return item.id === factId; })[0];
        var rows = [];
        state.evidence.forEach(function (key) {
          var parts = key.split('#');
          var scene = state.scenes.get(parts[0]);
          var statement = scene && scene.statements[Number(parts[1])];
          if (statement && statement.fact === factId) {
            rows.push(' [' + parts[0] + '] ' + statement.text);
          }
        });
        if (rows.length) {
          lines.push(' ' + factId + ' — ' + (fact ? fact.statement : ''));
          rows.forEach(function (row) { lines.push('   ' + row); });
        }
      });
      var missing = FACT_IDS.filter(function (id) { return !citedFacts().has(id); });
      if (missing.length) lines.push(' not cited: ' + missing.join(', '));
    }
    lines.push('');
    lines.push('FINAL EXPLANATION (as written at submit)');
    lines.push(state.submittedText || '(not submitted)');
    lines.push('');
    lines.push('CASE DEDUCTION (shown only after submit)');
    lines.push(' question: ' + state.truth.deduction.question);
    lines.push(' answer:   ' + state.truth.deduction.answer);
    lines.push('');
    lines.push('SELF-ASSESSMENT');
    lines.push(' ' + (state.selfCheck || '(not marked)'));
    lines.push('');
    lines.push('NOTE');
    lines.push(' This record was produced by a local page. It is testimony, not proof of play,');
    lines.push(' and it does not replace an independent non-author blind playtest.');
    return lines.join('\n') + '\n';
  }

  function showRecord() {
    if (!state.submitted) return;
    var area = $('record-text');
    area.value = buildRecord();
    area.hidden = false;
    area.focus();
    area.select();
    $('export-status').textContent = 'Text record shown below.';
  }

  function downloadRecord() {
    if (!state.submitted) return;
    var text = buildRecord();
    var area = $('record-text');
    area.value = text;
    area.hidden = false;
    try {
      var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var link = document.createElement('a');
      link.href = url;
      link.download = 'night-ferry-playtest-' + new Date().toISOString().replace(/[:.]/g, '-') + '.txt';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      $('export-status').textContent = 'Download requested. If nothing arrived, use “Show text record” and copy it.';
      log('exported playtest record');
    } catch (err) {
      $('export-status').textContent = 'Download unavailable here; the record is shown below to copy.';
    }
  }

  function copyRecord() {
    if (!state.submitted) return;
    var text = buildRecord();
    var area = $('record-text');
    area.value = text;
    area.hidden = false;
    function fallback() {
      area.focus();
      area.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
      $('export-status').textContent = ok ? 'Record copied.' : 'Copy was blocked; select the text record and copy it by hand.';
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        $('export-status').textContent = 'Record copied.';
      }, fallback);
    } else {
      fallback();
    }
  }

  /* ---------- wiring ---------- */

  function init() {
    $('load-files').addEventListener('change', function (event) {
      handleFiles(event.target.files);
      event.target.value = '';
    });
    $('load-fixture').addEventListener('click', function () {
      useFixture('Using the bundled fixture (placeholder text).');
    });
    $('submit').addEventListener('click', submitExplanation);
    $('export').addEventListener('click', downloadRecord);
    $('show-record').addEventListener('click', showRecord);
    $('copy-record').addEventListener('click', copyRecord);
    document.querySelectorAll('input[name="selfcheck"]').forEach(function (input) {
      input.addEventListener('change', function () {
        state.selfCheck = input.value;
        log('self-assessment: ' + input.value);
      });
    });
    window.addEventListener('beforeunload', function () { /* no storage, nothing to save */ });
    renderNotebook();
    renderRoute();
    boot();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
