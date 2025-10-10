import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { ServerDTO, CreateServerDTO } from './dto';

export const getServers = () =>
  api.get<never, AxiosResponse<ServerDTO[]>>('/servers');

export const createServer = (params: CreateServerDTO ) =>
  api.post<AxiosResponse>('servers', params, {
    headers: {
      'Content-Type': 'application/json',
    },
  });
