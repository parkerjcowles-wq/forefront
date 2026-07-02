// Forefront — frontend logic
(function () {
  "use strict";

  var form = document.getElementById("brief-form");
  var input = document.getElementById("company");
  var submit = document.getElementById("submit");
  var chips = document.getElementById("chips");
  var statusEl = document.getElementById("status");
  var statusText = document.getElementById("status-text");
  var errorEl = document.getElementById("error");
  var brief = document.getElementById("brief");
  var briefCompany = document.getElementById("brief-company");
  var briefEyebrow = document.getElementById("brief-eyebrow");
  var briefMeta = document.getElementById("brief-meta");
  var briefBody = document.getElementById("brief-body");
  var issueDate = document.getElementById("issue-date");

  if (window.marked) {
    marked.setOptions({ gfm: true, breaks: false });
  }

  var STAGES = [
    "Searching the live web…",
    "Reading the latest signals…",
    "Mapping the software stack…",
    "Profiling decision-makers…",
    "Drafting the brief…",
  ];
  var stageTimer = null;

  function today() {
    return new Date().toLocaleDateString("en-GB", {
      day: "numeric", month: "long", year: "numeric",
    });
  }
  if (issueDate) issueDate.textContent = today();

  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function startLoading(live) {
    hide(errorEl);
    hide(brief);
    submit.disabled = true;
    var i = 0;
    statusText.textContent = live ? STAGES[0] : "Pulling the dossier…";
    show(statusEl);
    if (live) {
      stageTimer = setInterval(function () {
        i = (i + 1) % STAGES.length;
        statusText.textContent = STAGES[i];
      }, 1600);
    }
  }

  function stopLoading() {
    if (stageTimer) { clearInterval(stageTimer); stageTimer = null; }
    hide(statusEl);
    submit.disabled = false;
  }

  function showError(msg) {
    stopLoading();
    errorEl.textContent = msg || "Something went wrong. Please try again.";
    show(errorEl);
  }

  function renderBrief(data) {
    stopLoading();
    briefCompany.textContent = data.company || "Account Brief";

    if (data.showcase) {
      briefEyebrow.textContent = "Sample Dossier";
      briefMeta.textContent = "Curated example · compiled from public sources";
    } else {
      briefEyebrow.textContent = "Account Brief";
      briefMeta.textContent =
        "Generated " + today() + " · " + (data.cached ? "from this session" : "live web research");
    }

    // Live briefs are synthesized from untrusted web content. Only inject HTML
    // when BOTH the renderer and the sanitizer loaded — otherwise fail closed
    // and render as plain text, never unsanitized HTML (e.g. if the DOMPurify
    // CDN is blocked or down).
    var md = data.markdown || "";
    if (window.marked && window.DOMPurify) {
      briefBody.innerHTML = DOMPurify.sanitize(marked.parse(md));
    } else {
      briefBody.textContent = md;
    }
    tagSourcesList();

    // Links (decision-maker search, sources) open in a new tab so the demo stays put.
    var links = briefBody.querySelectorAll("a[href]");
    for (var li = 0; li < links.length; li++) {
      links[li].target = "_blank";
      links[li].rel = "noopener noreferrer";
    }

    show(brief);
    brief.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Give the trailing Sources list its footnote styling.
  function tagSourcesList() {
    var heads = briefBody.querySelectorAll("h2");
    for (var i = 0; i < heads.length; i++) {
      if (/sources/i.test(heads[i].textContent)) {
        var n = heads[i].nextElementSibling;
        while (n) {
          if (n.tagName === "UL" || n.tagName === "OL") n.classList.add("sources");
          n = n.nextElementSibling;
        }
      }
    }
  }

  function readError(res) {
    return res.json().then(
      function (b) { return (b && b.error) || ("Request failed (" + res.status + ")."); },
      function () { return "Request failed (" + res.status + ")."; }
    );
  }

  function generate(company) {
    startLoading(true);
    fetch("/api/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company: company }),
    })
      .then(function (res) {
        if (!res.ok) return readError(res).then(function (m) { throw new Error(m); });
        return res.json();
      })
      .then(renderBrief)
      .catch(function (e) { showError(e.message); });
  }

  function loadShowcase(slug, label) {
    startLoading(false);
    fetch("/api/showcase/" + encodeURIComponent(slug))
      .then(function (res) {
        if (!res.ok) return readError(res).then(function (m) { throw new Error(m); });
        return res.json();
      })
      .then(renderBrief)
      .catch(function (e) { showError(e.message); });
    if (label) input.value = label;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var company = (input.value || "").trim();
    if (!company) { showError("Enter a company name to generate a brief."); return; }
    generate(company);
  });

  chips.addEventListener("click", function (e) {
    var btn = e.target.closest(".chip");
    if (!btn) return;
    loadShowcase(btn.getAttribute("data-slug"), btn.textContent.trim());
  });
})();
