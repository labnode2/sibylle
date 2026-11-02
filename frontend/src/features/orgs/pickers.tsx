// Choosing an avatar among the templates and a card background, as radio groups.
import { useTranslation } from 'react-i18next';

import type { PixelImage, Template } from '../../api/types';
import { PixelImage as Pixels } from '../../ui/PixelImage';
import styles from './orgs.module.css';

export function AvatarPicker({
  templates,
  value,
  onChange,
  labelId,
}: {
  templates: Template[];
  value: PixelImage | null;
  onChange: (image: PixelImage) => void;
  labelId: string;
}) {
  return (
    <div role="radiogroup" aria-labelledby={labelId} className={styles.choices}>
      {templates.map((template) => {
        const selected = value?.pixels === template.image.pixels;
        return (
          <button
            key={template.key}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={template.name}
            className={styles.choice}
            onClick={() => onChange(template.image)}
          >
            <Pixels image={template.image} size={48} avatar={false} />
          </button>
        );
      })}
    </div>
  );
}

export function BackgroundPicker({
  keys,
  value,
  onChange,
  labelId,
}: {
  keys: string[];
  value: string;
  onChange: (key: string) => void;
  labelId: string;
}) {
  const { t } = useTranslation('orgs');
  return (
    <div role="radiogroup" aria-labelledby={labelId} className={styles.choices}>
      {keys.map((key) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={value === key}
          aria-label={t(`backgrounds.${key}`)}
          className={styles.choice}
          onClick={() => onChange(key)}
        >
          <span className={`${styles.swatch} bg-${key}`} />
        </button>
      ))}
    </div>
  );
}
