import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { CertificateDTO, CreateCertificateDTO, EditCertificateDTO } from './dto';

export const getCertificates = () =>
  api.get<never, AxiosResponse<CertificateDTO[]>>('/certificates');

export const createCertificate = (params: CreateCertificateDTO) =>
  api.post<AxiosResponse>('/certificates', params, {
    headers: { 'Content-Type': 'application/json' },
  });

export const getCertificate = (id: string) => api.get<never, AxiosResponse<CertificateDTO>>(`/certificates/${id}`)

export const patchCertificate = (id: string, certificate: EditCertificateDTO) =>
  api.put(`/certificates/${id}`, certificate, {
    headers: { 'Content-Type': 'application/json' },
  });

export const deleteCertificate = (id: string) => api.delete(`/certificates/${id}`);
