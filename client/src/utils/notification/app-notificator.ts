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
class AppNotificator implements Notificator {
  public list: Map<number, Notice> = new Map();

  add = (notice: Notice) => {
    const id = Date.now();
    this.list.set(id, notice);
    this.show(notice, id);
    // TODO show on UI
    return id;
  };

  remove = (id: number) => {
    this.list.delete(id);
  };

  getAll = () => {
    return Array.from(this.list.values());
  };

  show = (notice: Notice, id?: number) => {
    // TODO
    alert(JSON.stringify(notice));
    if (id) {
      setTimeout(() => {
        this.remove(id)
      }, 300);
    }
  };
}

export const appNotificator = new AppNotificator();
