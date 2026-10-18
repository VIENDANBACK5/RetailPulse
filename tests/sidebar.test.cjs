const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../frontend/js/sidebar.js'), 'utf8');

function workspace(isMobile) {
  const classes = new Set();
  const documentEvents = new Map();
  const document = {
    body: { classList: {
      toggle(name, active) { active ? classes.add(name) : classes.delete(name); },
      contains(name) { return classes.has(name); },
    } },
    activeElement: null,
    addEventListener(name, handler) { documentEvents.set(name, handler); },
  };
  function element() {
    return {
      events: new Map(), attributes: {}, hidden: false,
      addEventListener(name, handler) { this.events.set(name, handler); },
      setAttribute(name, value) { this.attributes[name] = value; },
      focus() { document.activeElement = this; },
      click() { this.events.get('click')?.(); },
    };
  }
  const sidebar = element(), toggle = element(), close = element(), backdrop = element();
  const links = [element(), element()];
  sidebar.querySelectorAll = selector => selector === 'a' ? links : [close, ...links];
  const elements = { 'app-sidebar': sidebar, 'sidebar-toggle': toggle, 'sidebar-close': close, 'sidebar-backdrop': backdrop };
  document.getElementById = id => elements[id];
  const media = {
    matches: isMobile, events: new Map(),
    addEventListener(name, handler) { this.events.set(name, handler); },
  };
  vm.runInNewContext(source, { document, window: { matchMedia: () => media } });
  return {
    sidebar, toggle, close, backdrop, links, document, media,
    open: () => classes.has('sidebar-open'),
    key(key, shiftKey = false) {
      let prevented = false;
      documentEvents.get('keydown')({ key, shiftKey, preventDefault() { prevented = true; } });
      return prevented;
    },
  };
}

test('desktop navigation stays accessible without a modal backdrop', () => {
  const ui = workspace(false);
  assert.equal(ui.sidebar.inert, false);
  assert.equal(ui.backdrop.hidden, true);
  ui.toggle.click();
  assert.equal(ui.open(), false);
});

test('mobile menu opens accessibly and closes on backdrop click', () => {
  const ui = workspace(true);
  assert.equal(ui.sidebar.inert, true);
  ui.toggle.click();
  assert.equal(ui.open(), true);
  assert.equal(ui.toggle.attributes['aria-expanded'], 'true');
  assert.equal(ui.sidebar.inert, false);
  assert.equal(ui.backdrop.hidden, false);
  assert.equal(ui.document.activeElement, ui.close);
  ui.backdrop.click();
  assert.equal(ui.open(), false);
  assert.equal(ui.toggle.attributes['aria-expanded'], 'false');
  assert.equal(ui.sidebar.inert, true);
  assert.equal(ui.document.activeElement, ui.toggle);
});

test('Escape closes the drawer and restores focus to the opener', () => {
  const ui = workspace(true);
  ui.toggle.click();
  assert.equal(ui.key('Escape'), true);
  assert.equal(ui.open(), false);
  assert.equal(ui.document.activeElement, ui.toggle);
});

test('Tab and Shift+Tab keep focus inside an open mobile drawer', () => {
  const ui = workspace(true);
  ui.toggle.click();
  ui.links.at(-1).focus();
  assert.equal(ui.key('Tab'), true);
  assert.equal(ui.document.activeElement, ui.close);
  assert.equal(ui.key('Tab', true), true);
  assert.equal(ui.document.activeElement, ui.links.at(-1));
});

test('navigation closes the drawer without moving focus back to the opener', () => {
  const ui = workspace(true);
  ui.toggle.click();
  ui.links[0].focus();
  ui.links[0].click();
  assert.equal(ui.open(), false);
  assert.notEqual(ui.document.activeElement, ui.toggle);
});

test('resizing an open mobile drawer to desktop clears its modal state', () => {
  const ui = workspace(true);
  ui.toggle.click();
  ui.media.matches = false;
  ui.media.events.get('change')();
  assert.equal(ui.open(), false);
  assert.equal(ui.sidebar.inert, false);
  assert.equal(ui.backdrop.hidden, true);
});
