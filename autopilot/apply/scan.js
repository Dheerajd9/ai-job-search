// Enumerate fillable controls on an ATS application form.
// Returns [{id, kind, label, required, options[]}] and tags each control with
// data-ap-id so Python can address it. Works across Greenhouse / Lever / Ashby
// because it reads the accessibility tree (labels, aria, legends) not ATS ids.
() => {
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  const visible = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && st.display !== "none";
  };
  const byId = id => (id ? document.getElementById(id) : null);
  const textOf = el => clean(el ? (el.innerText || el.textContent) : "");

  const labelFor = el => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && textOf(l)) return textOf(l);
    }
    const lb = el.getAttribute("aria-labelledby");
    if (lb) {
      const t = lb.split(/\s+/).map(i => textOf(byId(i))).join(" ");
      if (clean(t)) return clean(t);
    }
    if (el.getAttribute("aria-label")) return clean(el.getAttribute("aria-label"));
    const wrap = el.closest("label");
    if (wrap && textOf(wrap)) return textOf(wrap);
    const fs = el.closest("fieldset");
    if (fs) {
      const lg = fs.querySelector("legend");
      if (lg && textOf(lg)) return textOf(lg);
    }
    // Lever/Ashby style: question text in a sibling block of a field wrapper
    let p = el.parentElement;
    for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
      const l = p.querySelector("label, .application-label, [class*='label'], [class*='Label'], [class*='question']");
      if (l && !l.contains(el) && textOf(l)) return textOf(l);
    }
    return clean(el.getAttribute("placeholder") || el.name || "");
  };

  const isRequired = (el, label) =>
    !!(el.required || el.getAttribute("aria-required") === "true" || /[*✱]\s*$|\(required\)/i.test(label));

  let n = 0;
  const tag = el => { const id = `ap${n++}`; el.setAttribute("data-ap-id", id); return id; };
  const out = [];
  const doneGroups = new Set();

  document.querySelectorAll("input, textarea, select").forEach(el => {
    if (el.closest("[data-ap-skip]")) return;
    const type = (el.getAttribute("type") || (el.tagName === "INPUT" ? "text" : el.tagName)).toLowerCase();
    if (["hidden", "submit", "button", "reset", "image", "search"].includes(type)) return;
    if (type !== "file" && !visible(el)) return;
    if (el.disabled || el.readOnly && el.getAttribute("role") !== "combobox") return;

    if (type === "radio" || type === "checkbox") {
      const name = el.name;
      const group = name ? Array.from(document.querySelectorAll(`input[name="${CSS.escape(name)}"]`)) : [el];
      if (type === "checkbox" && group.length <= 1) {
        const label = labelFor(el);
        out.push({id: tag(el), kind: "checkbox", label, required: isRequired(el, label), options: []});
        return;
      }
      if (doneGroups.has(name)) return;
      doneGroups.add(name);
      const fs = el.closest("fieldset");
      let container = fs, label = fs && fs.querySelector("legend") ? textOf(fs.querySelector("legend")) : "";
      if (!label) {
        // walk up until a label-ish element that is not one of the option labels
        let p = el.parentElement;
        for (let i = 0; i < 5 && p && !label; i++, p = p.parentElement) {
          const cands = p.querySelectorAll("legend, .application-label, [class*='label'], [class*='Label'], [class*='question-title'], label");
          for (const l of cands) {
            if (group.some(o => l.contains(o)) || (l.htmlFor && group.some(o => o.id === l.htmlFor))) continue;
            if (textOf(l)) { label = textOf(l); container = p; break; }
          }
        }
      }
      container = container || el.parentElement;
      const opts = group.map(o => {
        const ol = o.id && document.querySelector(`label[for="${CSS.escape(o.id)}"]`);
        return clean(ol ? textOf(ol) : (o.closest("label") ? textOf(o.closest("label")) : o.value));
      });
      group.forEach((o, i) => o.setAttribute("data-ap-opt", String(i)));
      const gid = tag(container || el);
      group.forEach(o => o.setAttribute("data-ap-group", gid));
      out.push({id: gid, kind: type === "radio" ? "radio" : "checkbox-group", label,
                required: group.some(o => o.required) || /[*✱]\s*$/.test(label), options: opts});
      return;
    }

    const label = labelFor(el);
    let kind = el.tagName === "TEXTAREA" ? "textarea" : el.tagName === "SELECT" ? "select" : type;
    if (el.getAttribute("role") === "combobox" || el.getAttribute("aria-autocomplete") === "list") kind = "combobox";
    const options = kind === "select" ? Array.from(el.options).map(o => clean(o.text)) : [];
    out.push({id: tag(el), kind, label, required: isRequired(el, label), options});
  });

  // Ashby-style Yes/No button pairs (no underlying input)
  document.querySelectorAll("button").forEach(b => {
    if (!/^(yes|no)$/i.test(textOf(b)) || b.closest("[data-ap-id]")) return;
    const box = b.parentElement;
    if (!box || box.hasAttribute("data-ap-id")) return;
    const btns = Array.from(box.querySelectorAll("button")).filter(x => visible(x));
    if (btns.length < 2) return;
    let p = box.parentElement, label = "";
    for (let i = 0; i < 3 && p && !label; i++, p = p.parentElement) {
      const l = p.querySelector("label, [class*='label'], [class*='Label']");
      if (l && !box.contains(l)) label = textOf(l);
    }
    btns.forEach((x, i) => x.setAttribute("data-ap-opt", String(i)));
    out.push({id: tag(box), kind: "buttons", label, required: /[*✱]\s*$/.test(label),
              options: btns.map(textOf)});
  });
  return out;
}
