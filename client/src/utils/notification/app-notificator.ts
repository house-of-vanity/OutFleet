export type NoticeType = 'success' | 'error' | 'warn';
export interface Notice {
  message: string;
  type: NoticeType;
}
export interface Notificator {
  list: Map<number, Notice>;
  add: (notice: Notice) => number;
  remove: (id: number) => void;
  getAll: () => Notice[];
}

export interface INotificatorViewProvider<T = Record<string, unknown>> {
  paramsMappers: (notice: Notice) => T;
  show: (params: T) => void;
}

class AppNotificator implements Notificator {
  public list: Map<number, Notice> = new Map();
  private viewProvider: INotificatorViewProvider | null = null;

  add = (notice: Notice) => {
    const id = Date.now();
    this.list.set(id, notice);
    this.show(notice, id);
    // TODO show on UI
    return id;
  };

  applyProvider = <T extends Record<string, unknown>>(
    provider: INotificatorViewProvider<T>,
  ) => {
    (this.viewProvider as INotificatorViewProvider<T>) = provider;
  };

  remove = (id: number) => {
    this.list.delete(id);
  };

  getAll = () => {
    return Array.from(this.list.values());
  };

  show = (notice: Notice, id?: number) => {
    if (this.viewProvider) {
      const { paramsMappers, show } = this.viewProvider;
      const params = paramsMappers(notice);
      show(params);
    } else {
      alert(JSON.stringify(notice));
    }
    if (id) {
      setTimeout(() => {
        this.remove(id);
      }, 300);
    }
  };
}

export const appNotificator = new AppNotificator();
