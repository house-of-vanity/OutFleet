import { api } from './api';

export interface User {}

export const getUsers = api.get<never, User[]>('/users');
