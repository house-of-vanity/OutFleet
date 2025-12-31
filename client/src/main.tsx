import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router/dom';
import { store } from './store/store';
import { Provider } from 'react-redux';
import { HeroUIProvider } from '@heroui/react';
import {ToastProvider} from "@heroui/toast";
import { router } from './router';
import './index.css';
import { ApplyNotificator } from './common/components/apply-notificator';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <HeroUIProvider>
        <RouterProvider router={router} />
        <ToastProvider/>
        <ApplyNotificator/>
      </HeroUIProvider>
    </Provider>
  </StrictMode>,
);
