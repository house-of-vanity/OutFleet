import { Link, useLocation } from 'react-router';
import { clsx } from 'clsx';

interface NavMenuItems {
  href: string;
  label: string;
}

interface NavMenuProps {
  items: NavMenuItems[];
}

export const NavMenu = (props: NavMenuProps) => {
  const { items } = props;
  const { pathname } = useLocation();

  return (
    <div className="tabs">
      {items.map(({ href, label }) => (
        <Link
          className={clsx('tab', {
            active: href === pathname,
          })}
          to={href}
        >
          {label}
        </Link>
      ))}
    </div>
  );
};
