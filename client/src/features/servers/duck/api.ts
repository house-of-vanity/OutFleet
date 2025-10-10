import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { ServerDTO } from './dto';

export const getServers = () => api.get<never, AxiosResponse<ServerDTO[]>>('/servers');
