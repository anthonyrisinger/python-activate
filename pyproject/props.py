class config:
    """Configurable property decorator.

    Pass config:
        @prop(name)

    Pass nothing:
        @prop()
        @prop

    Both are handled consistently.
    """

    class INSTANCE:
        class GET:
            pass

    class OWNER:
        class GET:
            pass

    # Check for either.
    GET = (OWNER.GET, INSTANCE.GET)

    def __init__(self, *args, name=None, **kwds):
        """Store decorated function config."""
        self.name = name
        for kv in kwds.items():
            # Push through property (if any) for normalization.
            setattr(self, *kv)
        if args:
            self(*args)

    def __call__(self, fun):
        """Store decorated function."""
        self.fun = fun
        self.name = self.name or fun.__name__
        return self

    def __set_name__(self, owner, name):
        """Prefer name from classdef."""
        self.name = name

    def __get__(self, instance, owner):
        cls = self.OWNER.GET if instance is None else self.INSTANCE.GET
        context = cls()
        context.config = self
        value = self.fun(instance, context)
        return value


class caching(config):

    def __init__(self, *args, cache=True, **kwds):
        super().__init__(*args, cache=cache, **kwds)

    def __get__(self, instance, owner):
        cache = self.cache
        value = super().__get__(instance, owner)
        if isinstance(value, self.GET):
            # Value is a marker.
            cache = getattr(value, 'cache', cache)
            value = getattr(value, 'value', value)

        if instance is None:
            # Nowhere to cache things.
            return value

        if cache:
            # Python will stop calling us now.
            instance.__dict__[self.name] = value

        return value


class attribute(caching):

    class INSTANCE(config.INSTANCE):
        class SET:
            pass

    class OWNER(config.OWNER):
        class SET:
            pass

    # Check for either.
    SET = (OWNER.SET, INSTANCE.SET)

    def __get__(self, instance, owner):
        try:
            value = instance.__dict__[self.name]
        except KeyError:
            value = super().__get__(instance, owner)
        except AttributeError:
            value = self
        return value

    def __set__(self, instance, value):
        context = self.INSTANCE.SET()
        context.config = self
        context.value = value
        value = self.fun(instance, context)
        if value is context:
            value = getattr(value, 'value', value)
        super().__set__(instance, value)


class modelattribute(config):

    def __init__(self, *args, model, collection=True, **kwds):
        model = getattr(model, '_model', model)
        kwds.update(model=model, collection=collection)
        super().__init__(*args, **kwds)

    def __set__(self, instance, value):
        if value is None:
            return

        try:
            value = value.items
        except AttributeError:
            vals = list(value)
        else:
            vals = list(value())

        for i, keyval in enumerate(vals):
            try:
                key, val = () + keyval
            except TypeError:
                key, val = None, keyval
            if getattr(val, '_model', None) == 'val':
                val = val._clone()
            elif key is None:
                val = models.from_config(val)
            else:
                val = models.from_keyconfig(key, val)
            # Replace with reified val.
            vals[i] = val

        vals = utils.namespace((val.key,val) for val in vals)
        defaults = vals.get('_/_')
        if defaults is not None:
            for key, val in vals.items():
                clone = defaults._clone()._merge(val)
                vals[key] = clone
            # Merging in defaults could update the key.
            vals = {val.key: val for val in vals.values()}

        return vals
