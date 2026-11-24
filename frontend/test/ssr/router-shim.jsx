// Stand-in for react-router-dom, used ONLY by the SSR smoke test when the real package is not installed
// (the sandbox this project was written in had no network access). With `npm install` done, the real one is used.
import { createContext, createElement, useContext } from 'react';

const Ctx = createContext({ pathname: '/', search: '' });

export function MemoryRouter({ initialEntries = ['/'], children }) {
  const [pathname, search = ''] = String(initialEntries[0]).split('?');
  return createElement(Ctx.Provider, { value: { pathname, search: search ? `?${search}` : '' } }, children);
}
export const useLocation = () => ({ ...useContext(Ctx), state: null });
export const useNavigate = () => () => {};
export function useSearchParams() { return [new URLSearchParams(useContext(Ctx).search), () => {}]; }
export function Link({ to, children, ...rest }) {
  const href = typeof to === 'string' ? to : `${to.pathname || ''}${to.search || ''}`;
  return createElement('a', { href, ...rest }, children);
}
export function NavLink({ to, children, className, end: _end, ...rest }) {
  const { pathname } = useContext(Ctx);
  const active = pathname === to;
  const cls = typeof className === 'function' ? className({ isActive: active }) : className;
  return createElement('a', { href: to, className: cls, 'aria-current': active ? 'page' : undefined, ...rest },
    typeof children === 'function' ? children({ isActive: active }) : children);
}
export const Navigate = () => null;
export const Routes = ({ children }) => children;
export const Route = () => null;
export const BrowserRouter = ({ children }) => children;
