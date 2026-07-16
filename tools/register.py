# GPL License

import bpy

__bl_classes = []
__bl_ordered_classes = []
__bl_registered_classes = []


def register_wrap(cls):
    cls = make_annotations(cls)
    if hasattr(cls, 'bl_rna') and cls not in __bl_classes:
        __bl_classes.append(cls)
    return cls


def make_annotations(cls):
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, bpy.props._PropertyDeferred)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls


def order_classes():
    global __bl_ordered_classes
    classes_to_register = list(dict.fromkeys(iter_classes_to_register()))
    own_classes = set(classes_to_register)
    deps_dict = {}
    for cls in classes_to_register:
        deps_dict[cls] = set(iter_own_register_deps(cls, own_classes))

    # Preserve module discovery order for unrelated classes, while preferring
    # operators and property groups before UI classes. Extension modules are
    # namespaced as bl_ext.<repository>.<extension>.ui.*, so checking only for
    # a module name that starts with "ui." is not sufficient.
    __bl_ordered_classes = toposort(deps_dict, classes_to_register)
    return tuple(__bl_ordered_classes)


def register_classes():
    global __bl_registered_classes

    if __bl_registered_classes:
        raise RuntimeError("CATS classes are already registered")

    ordered_classes = order_classes()
    registered_classes = []
    try:
        for cls in ordered_classes:
            bpy.utils.register_class(cls)
            registered_classes.append(cls)
    except Exception as exc:
        for registered_cls in reversed(registered_classes):
            try:
                bpy.utils.unregister_class(registered_cls)
            except Exception as rollback_exc:
                print(
                    "CATS: failed to roll back class "
                    f"{registered_cls.__module__}.{registered_cls.__name__}: {rollback_exc}"
                )
        failed_class = f"{cls.__module__}.{cls.__name__}"
        raise RuntimeError(f"CATS failed to register class {failed_class}") from exc

    __bl_registered_classes = registered_classes
    return len(registered_classes)


def unregister_classes():
    global __bl_registered_classes

    classes_to_unregister = list(reversed(__bl_registered_classes))
    errors = []
    count = 0

    for cls in classes_to_unregister:
        try:
            bpy.utils.unregister_class(cls)
            count += 1
        except Exception as exc:
            errors.append((cls, exc))

    # Retain failed classes in their original registration order so a second
    # cleanup attempt can retry them instead of losing track of Blender state.
    __bl_registered_classes = list(reversed([cls for cls, _ in errors]))

    if errors:
        failed_names = ", ".join(f"{cls.__module__}.{cls.__name__}" for cls, _ in errors)
        raise RuntimeError(f"CATS failed to unregister classes: {failed_names}") from errors[0][1]

    return count


def iter_classes_to_register():
    for cls in __bl_classes:
        yield cls


def iter_own_register_deps(cls, own_classes):
    yield from (dep for dep in iter_register_deps(cls) if dep in own_classes)


def iter_register_deps(cls):
    for value in getattr(cls, '__annotations__', {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None:
            yield dependency


def get_dependency_from_annotation(value):
    if isinstance(value, bpy.props._PropertyDeferred):
        if value.function in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
            return value.keywords.get("type")
    if isinstance(value, tuple) and len(value) == 2:
        if value[0] in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
            return value[1].get("type")
    return None


# Find order to register to solve dependencies
#################################################

def _is_ui_class(cls):
    return 'ui' in cls.__module__.split('.')


def toposort(deps_dict, discovery_order=None):
    deps_dict = {value: set(deps) for value, deps in deps_dict.items()}
    discovery_order = discovery_order or list(deps_dict)
    order_index = {cls: index for index, cls in enumerate(discovery_order)}
    sorted_list = []

    while deps_dict:
        ready = [value for value, deps in deps_dict.items() if not deps]
        if not ready:
            unresolved = ', '.join(
                f"{value.__module__}.{value.__name__}"
                for value in sorted(deps_dict, key=lambda cls: order_index.get(cls, 0))
            )
            raise RuntimeError(f"Cyclic CATS class registration dependencies: {unresolved}")

        ready.sort(key=lambda cls: (_is_ui_class(cls), order_index.get(cls, 0)))
        next_class = ready[0]
        sorted_list.append(next_class)
        deps_dict = {
            value: deps - {next_class}
            for value, deps in deps_dict.items()
            if value is not next_class
        }

    return sorted_list
