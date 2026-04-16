export type SSEMessage<T> = {
  event: string;
  data: T;
};

export function createEventStream<T>(
  url: string,
  onMessage: (message: SSEMessage<T>) => void,
  onError?: (error: Event) => void
): EventSource {
  const source = new EventSource(url);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as T;
      onMessage({ event: "message", data });
    } catch {
      onMessage({ event: "message", data: event.data as T });
    }
  };

  source.onerror = (error) => {
    if (onError) {
      onError(error);
    }
  };

  return source;
}
