/** Picks the Kazakh name when the UI is in Kazakh and it exists, otherwise Russian. */
export function localName(
  item: { name_ru: string; name_kk?: string | null },
  language: string | undefined,
): string {
  return language === 'kk' && item.name_kk ? item.name_kk : item.name_ru;
}

export const allergenName = localName;
export const dishName = localName;
