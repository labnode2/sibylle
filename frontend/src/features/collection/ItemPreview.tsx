// How an object of the collection looks: a colour swatch, a frame around the member's avatar,
// or the crystal ball's variant from the kit.
import type { PixelImageData } from '../../ui/PixelImage';
import { CrystalBall } from '../../ui/CrystalBall';
import { FramedAvatar } from '../../ui/FramedAvatar';
import type { Variant } from '../../vendor/crystal-ball/crystal-ball.js';
import type { CatalogItem } from '../profile/api';
import styles from './collection.module.css';

export function ItemPreview({
  item,
  avatar,
  size = 48,
}: {
  item: CatalogItem;
  avatar: PixelImageData;
  size?: number;
}) {
  if (item.kind === 'color') {
    return (
      <span
        className={styles.swatch}
        style={{ background: String(item.data.hex), width: size, height: size }}
      />
    );
  }
  if (item.kind === 'frame') {
    return <FramedAvatar image={avatar} frame={item.key} size={size - 12} />;
  }
  return <CrystalBall variant={String(item.data.variant) as Variant} size={size} />;
}
