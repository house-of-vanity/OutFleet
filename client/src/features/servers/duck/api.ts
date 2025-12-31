import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { ServerDTO, CreateServerDTO, TestServerDTO } from './dto';

export const getServers = () =>
  api.get<never, AxiosResponse<ServerDTO[]>>('/servers');

export const createServer = (params: CreateServerDTO) =>
  api.post<AxiosResponse>('servers', params, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

export const testServer = (id: string) =>
  api.post<TestServerDTO>(`/servers/${id}/test`);

export const deleteServer = (id: string) => api.delete(`/servers/${id}`);

export const getServer = (id: string) =>
  api.get<string, AxiosResponse<ServerDTO>>(`/servers/${id}`);

export const patchServer = (id: string, server: CreateServerDTO) =>
  api.put(`/servers/${id}`, server, {
    headers: { 'Content-Type': 'application/json' },
  });


