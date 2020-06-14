#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import update_wrapper, wraps


def disable(func):
    '''
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def decorator(func):
    '''
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    '''
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.__doc__ = func.__doc__
    wrapper.__name__ = func.__name__
    wrapper.__dict__.update(func.__dict__)
    return wrapper


def countcalls(func):
    '''Decorator that counts calls made to the function decorated.'''
    @wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1
        return func(*args, **kwargs)
    wrapper.calls = 0
    return wrapper


def memo(func):
    '''
    Memoize a function so that it caches all return values for
    faster future lookups.
    '''
    d = {}
    @wraps(func)
    def wrapper(*args, **kwargs):
        if args not in d:
            res = func(*args, **kwargs)
            d[args] = res
        else:
            res = d[args]
        return res
    return wrapper


def n_ary(func):
    '''
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        if len(args) == 1:
            res = args[0]
        elif len(args) == 2:
            res = func(*args, **kwargs)
        else:
            res = func(args[0], eval(f'{func.__name__}{args[1:]}'))
        return res
    return wrapper


def trace(filler='____'):
    '''Trace calls made to function decorated'''
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f'{filler*wrapper.count} --> {func.__name__}({args[0]})')
            wrapper.count += 1
            res = func(*args, **kwargs)
            wrapper.count -= 1
            print(f'{filler*wrapper.count} <-- {func.__name__}({args[0]})={res}')
            return res
        wrapper.count = 0
        return wrapper
    return decorator


@memo
@countcalls
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


@countcalls
@trace("####")
@memo
def fib(n):
    """Some doc"""
    return 1 if n <= 1 else fib(n-1) + fib(n-2)


def main():
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, 'calls made')


if __name__ == '__main__':
    main()
