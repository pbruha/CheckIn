// Nastaví adresu serveru z proměnné CHECKIN_URL, např. http://192.168.1.20:8080 nebo https://checkin.skola.cz
import { readFileSync, writeFileSync } from 'node:fs';

const url = process.env.CHECKIN_URL;
if (!url || !/^https?:\/\//.test(url)) {
  console.error('Nastavte CHECKIN_URL, např. CHECKIN_URL=http://192.168.1.20:8080');
  process.exit(1);
}
const path = new URL('../capacitor.config.json', import.meta.url);
const config = JSON.parse(readFileSync(path, 'utf8'));
config.server.url = url;
// Cleartext (http) je povolen jen pro vývojovou adresu; HTTPS adresu ponecháme bez něj.
config.server.cleartext = url.startsWith('http://');
writeFileSync(path, JSON.stringify(config, null, 2) + '\n');
console.log(`Adresa serveru nastavena na ${url}`);
