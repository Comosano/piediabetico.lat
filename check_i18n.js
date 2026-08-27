const fs = require('fs');

const html = fs.readFileSync('frontend/index.html', 'utf8');
const js = fs.readFileSync('frontend/app.js', 'utf8');

const regex = /data-i18n="([^"]+)"/g;
const keysInHtml = new Set();
let m;
while ((m = regex.exec(html)) !== null) {
  keysInHtml.add(m[1]);
}

const fn = new Function('window', 'document', 'localStorage', 'navigator', 'Intl', js + '; return i18nTranslations;');
const mockStorage = { getItem: () => null, setItem: () => null };
const mockDoc = { addEventListener: () => null, querySelectorAll: () => [], getElementById: () => null };
const mockNav = { language: 'es' };
const mockWin = { scrollTo: () => null, lucide: { createIcons: () => null } };

let trans;
try {
  trans = fn(mockWin, mockDoc, mockStorage, mockNav, Intl);
} catch (e) {
  console.error('Error evaluating i18nTranslations:', e.message);
  process.exit(1);
}

console.log('Total unique data-i18n keys in HTML:', keysInHtml.size);

let hasError = false;
['es', 'pt', 'en'].forEach(lang => {
  const missing = [];
  keysInHtml.forEach(k => {
    if (!trans[lang] || !trans[lang][k]) {
      missing.push(k);
    }
  });
  if (missing.length > 0) {
    console.log('Missing in ' + lang + ' (' + missing.length + '):', missing);
    hasError = true;
  } else {
    console.log('Language [' + lang + ']: 100% OK (' + keysInHtml.size + '/' + keysInHtml.size + ' keys)');
  }
});

if (hasError) {
  process.exit(1);
} else {
  console.log('ALL I18N KEYS FULLY TRANSLATED AND MATCHED!');
}
