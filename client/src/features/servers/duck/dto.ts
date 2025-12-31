export interface ServerDTO {
    id: string
    name: string
    hostname: string
    grpc_port: number
    status: string
}

export interface CreateServerDTO {
  name: string;
  hostname: string;
  grpc_port: number;
}

export interface TestServerDTO {
  connected: boolean,
  endpoint: string
}
