import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { CertificateDTO } from './dto';

export const getCertificates = () =>
  api.get<never, AxiosResponse<CertificateDTO[]>>('/certificates');
