import { useForm, type SubmitHandler } from 'react-hook-form'
import type { CreateTemplateForm } from '../../types';
import { useAppDispatch } from '../../../../common/hooks';
import { protocolOptions } from './util'
import type { CreateTemplateDTO } from '../../duck/dto';
import { createTemplateAction } from '../../duck';


export const AddTemplate = () => {
    const dispatch = useAppDispatch()
    const { register, handleSubmit, reset } = useForm<CreateTemplateForm>({
        defaultValues: {
            default_port: '443'
        }
    });

    const onSubmit: SubmitHandler<CreateTemplateForm> = (values) => {
       const data: CreateTemplateDTO = {
            ...values,
            default_port: parseInt(values.default_port),
            config_template: ''
        }
        dispatch(createTemplateAction(data)).then(() => {
          reset();
        });
      };


    return (
        <form onSubmit={handleSubmit(onSubmit)} id="templateForm">
          <div className="form-group">
            <label>Name:</label>
            <input type="text" {...register('name', { required: true })} />
          </div>
          <div className="form-group">
            <label>Protocol:</label>
            <select {...register('protocol', {required: true})}>
                {Object.entries(protocolOptions).map((protocolTupple)=> (
                    <option value={protocolTupple[0]}>{protocolTupple[1]}</option>
                ))}
            </select>
          </div>
          <div className="form-group">
            <label>Default Port:</label>
            <input type="number" {...register('default_port', {required: true})} />
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" {...register('requires_tls')}/> Requires TLS
            </label>
          </div>
          <button type="submit" className="btn btn-primary">
            Add Template
          </button>
        </form>
    )
}