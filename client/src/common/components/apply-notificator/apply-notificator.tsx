import {addToast, type ToastProps} from "@heroui/toast";

import { useEffect } from 'react';
import {
  appNotificator,
  type Notice,
  type NoticeType,
} from '../../../utils/notification/app-notificator';

const colorMap = new Map<NoticeType, string>([
  ['success', 'Success'],
  ['error', 'Danger'],
  ['warn', 'Warning'],
]);

const paramsMappers = (notice: Notice): Partial<ToastProps> => {
  const { type, message } = notice;
  const color = colorMap.get(type);
  return {
    description: message,
    color: color?.toLowerCase() as ToastProps['color'],
  };
};

export const ApplyNotificator = () => {
  useEffect(() => {
    appNotificator.applyProvider({
      paramsMappers,
      show: (params: Partial<ToastProps>) => addToast(params),
    });
  }, []);
  return <></>;
};
