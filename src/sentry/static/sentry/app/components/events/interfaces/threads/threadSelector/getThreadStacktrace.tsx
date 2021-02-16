import {ExceptionType} from 'app/types';
import {Event} from 'app/types/event';
import {Thread} from 'app/types/events';

import getThreadException from './getThreadException';

function getThreadStacktrace(
  event: Event,
  raw: boolean,
  thread?: Thread,
  exception?: Required<ExceptionType>
) {
  if (!thread) {
    return undefined;
  }

  const threadException = exception ?? getThreadException(event, thread);

  if (threadException) {
    const threadExceptionValues = threadException.values;

    const matchedStacktraceAndExceptionThread = threadExceptionValues.find(
      threadExceptionValue =>
        threadExceptionValue.threadId === thread.id && threadExceptionValue.stacktrace
    );

    // When a exception value matches the threadId, it means that the stack traces are the same
    // and we don't want to display the same info 2x in the UI
    if (matchedStacktraceAndExceptionThread) {
      return undefined;
    }

    // In the getThreadException function, when threadIds don't match the activeThread id and the activeThread is 'crashed' and
    // when at least one exception stack trace is found in the exception values, the function returns the exception data.
    // When this happen undefined has to be returned here
    if (thread.crashed) {
      const exceptionHasAtLeastOneStacktrace = !!threadExceptionValues.find(
        threadExceptionValue => threadExceptionValue.stacktrace
      );

      if (!!exceptionHasAtLeastOneStacktrace) {
        return undefined;
      }
    }
  }

  if (raw && thread.rawStacktrace) {
    return thread.rawStacktrace;
  }

  if (thread.stacktrace) {
    return thread.stacktrace;
  }

  return undefined;
}

export default getThreadStacktrace;
