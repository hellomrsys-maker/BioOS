import io
import os

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _read(name):
    with io.open(os.path.join(WEB, name), "r", encoding="utf-8") as f:
        return f.read()


def _extract_after(line, marker, terminator):
    if marker not in line:
        return None
    start = line.index(marker) + len(marker)
    end = line.find(terminator, start)
    if end == -1:
        return None
    return line[start:end]


def _referenced_ids(js):
    ids = set()
    for line in js.splitlines():
        for marker in ("getElementById('", 'getElementById("'):
            value = _extract_after(line, marker, marker[-1])
            if value:
                ids.add(value)
    return ids


def _defined_ids(html):
    ids = set()
    for line in html.splitlines():
        value = _extract_after(line, 'id="', '"')
        if value:
            ids.add(value)
    return ids


def _inline_handlers(html):
    handlers = set()
    for line in html.splitlines():
        for marker in ('oninput="', 'onclick="', 'onchange="'):
            value = _extract_after(line, marker, '(')
            if value and value.isidentifier():
                handlers.add(value)
    return handlers


def _defined_functions(js):
    fns = set()
    for line in js.splitlines():
        stripped = line.strip()
        if stripped.startswith('function ') or stripped.startswith('async function '):
            value = _extract_after(stripped.replace('async ', '', 1), 'function ', '(')
            if value and value.isidentifier():
                fns.add(value)
    return fns


def _toggled_classes(js):
    classes = set()
    for marker in ("classList.add('", "classList.remove('", "classList.toggle('"):
        for line in js.splitlines():
            value = _extract_after(line, marker, "'")
            if value:
                classes.add(value)
    return classes


def test_every_referenced_dom_id_exists_in_html():
    missing = sorted(_referenced_ids(_read('app.js')) - _defined_ids(_read('index.html')))
    assert not missing, 'DOM ids missing from index.html: ' + repr(missing)


def test_every_inline_handler_is_defined_in_js():
    missing = sorted(_inline_handlers(_read('index.html')) - _defined_functions(_read('app.js')))
    assert not missing, 'inline handlers missing from app.js: ' + repr(missing)


def test_state_classes_toggled_by_js_have_css_rules():
    css = _read('style.css')
    for cls in sorted(_toggled_classes(_read('app.js'))):
        assert ('.' + cls) in css, 'style.css missing rule for toggled class: ' + cls


def test_alpha_floor_stall_styling_applies_to_the_real_card():
    assert '.alpha-floor-card.stall' in _read('style.css')


def test_news2_panel_ids_wired():
    html = _read('index.html')
    js = _read('app.js')
    for element_id in ('ewsPatientsBody', 'ewsPatientSelect', 'ewsResultBox',
                       'ewsAlertFeed', 'ewsLowChip', 'ewsMediumChip', 'ewsHighChip'):
        assert ('id="' + element_id + '"') in html, 'missing element: ' + element_id
        assert element_id in js, 'not wired in app.js: ' + element_id


def test_hazard_h11_override_semantics_in_observation_form():
    js = _read('app.js')
    assert ('payload.is_alert = !document.getElementById(' + chr(39) + 'ewsAlertState' + chr(39) + ').checked') in js


if __name__ == '__main__':
    test_every_referenced_dom_id_exists_in_html()
    test_every_inline_handler_is_defined_in_js()
    test_state_classes_toggled_by_js_have_css_rules()
    test_alpha_floor_stall_styling_applies_to_the_real_card()
    test_news2_panel_ids_wired()
    test_hazard_h11_override_semantics_in_observation_form()
    print('ALL WEB DOM CONSISTENCY TESTS PASSED!')