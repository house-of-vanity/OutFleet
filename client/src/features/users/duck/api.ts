import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { UserDTO } from './dto';

export const getUsers = () => api.get<never, AxiosResponse<UserDTO[]>>('/users');
