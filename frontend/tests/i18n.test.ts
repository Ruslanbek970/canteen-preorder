import en from '@/i18n/en.json';
import kk from '@/i18n/kk.json';
import ru from '@/i18n/ru.json';

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe('i18n resources', () => {
  it('kk and en have the same keys as ru', () => {
    const ruKeys = keys(ru).sort();
    expect(keys(kk).sort()).toEqual(ruKeys);
    expect(keys(en).sort()).toEqual(ruKeys);
  });
});
