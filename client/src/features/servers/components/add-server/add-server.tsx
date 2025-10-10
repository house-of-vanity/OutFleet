import { useForm, type SubmitHandler } from 'react-hook-form';
import { createServerAction } from '../../duck';
import { useAppDispatch } from '../../../../common/hooks';
import type { CreateServerForm } from './types';



export const AddServer = () => {
  const dispatch = useAppDispatch();
  const { register, handleSubmit, reset } = useForm<CreateServerForm>();

  const onSubmit: SubmitHandler<CreateServerForm> = (values) => {
    const data = {
        ...values,
        grpc_port: parseInt(values.grpc_port)
    }
    dispatch(createServerAction(data)).then(() => {
      reset();
    });
  };

  return (
    <div className="section">
      <h2>Add Server</h2>
      <form onSubmit={handleSubmit(onSubmit)} id="serverForm">
        <div className="form-group">
          <label>Name:</label>
          <input {...register('name', { required: true })} />
        </div>
        <div className="form-group">
          <label>Hostname:</label>
          <input {...register('hostname', { required: true })} />
        </div>
        <div className="form-group">
          <label>gRPC Port:</label>
          <input {...register('grpc_port', { required: true })} />
        </div>
        <button type="submit" className="btn btn-primary">
          Add Server
        </button>
      </form>
    </div>
  );
};
