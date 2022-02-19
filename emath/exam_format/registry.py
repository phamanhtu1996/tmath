from django.utils import six

formats = {}

def registry_exam_format(name):
    def registry_class(exam_format_class):
        assert name not in formats
        formats[name] = exam_format_class
        return exam_format_class
    
    return registry_class

def choices():
    return [(key, value.name) for key, value in sorted(six.iteritems(formats))]