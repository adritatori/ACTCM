/* ACTCM Contribute wizard. Builds a link to a GitHub issue form with some fields filled in.
   GitHub fills a field from a URL parameter named after the field's id. Nothing is sent from this page. */
const form = document.getElementById("wizard");
const go = document.getElementById("w-go");
const repo = form.dataset.repo;
const MAX = 8000;

function kind() { return form.querySelector('input[name="kind"]:checked').value; }

function build() {
  const k = kind();
  const q = new URLSearchParams({ template: k });
  form.querySelectorAll('[data-for="' + k + '"] [data-field]').forEach(el => {
    const v = el.value.trim();
    if (v) q.set(el.dataset.field, v);
  });
  let url = "https://github.com/" + repo + "/issues/new?" + q.toString();
  if (url.length > MAX) url = "https://github.com/" + repo + "/issues/new?template=" + encodeURIComponent(k);
  go.href = url;
}

function show() {
  const k = kind();
  form.querySelectorAll("[data-for]").forEach(d => { d.hidden = d.dataset.for !== k; });
  build();
}

const quote = document.getElementById("w-quote"), qn = document.getElementById("w-quote-n");
quote.addEventListener("input", () => {
  const n = quote.value.trim() ? quote.value.trim().split(/\s+/).length : 0;
  qn.textContent = n + " of 25 words" + (n > 25 ? ": too long, please shorten it" : "");
});

form.addEventListener("input", build);
form.addEventListener("change", show);
form.addEventListener("submit", e => e.preventDefault());

/* a step id passed in the address, for example contribute.html#review=hf-2026-07/s17 */
const m = /^#(review|dispute)=([a-z0-9-]+\/s\d+)$/.exec(location.hash);
if (m) {
  const k = m[1] === "review" ? "step-review.yml" : "step-dispute.yml";
  form.querySelector('input[value="' + k + '"]').checked = true;
  form.querySelector('[data-for="' + k + '"] [data-field="step_id"]').value = m[2];
}
form.hidden = false;
document.getElementById("wizard-plain").hidden = true;
show();
document.documentElement.setAttribute("data-ready", "1");
