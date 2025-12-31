import { createBrowserRouter } from 'react-router';
import {
  Home,
  DashboardRoute,
  ServersRoute,
  InboundTemplatesRoute,
  CertificatesRoute,
  InboundBindingRoute,
  UsersRoute,
} from '../pages';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Home,
    children: [
      DashboardRoute,
      ServersRoute,
      InboundTemplatesRoute,
      CertificatesRoute,
      InboundBindingRoute,
      UsersRoute,
    ],
  },
]);
