import bluesky
from bluesky.tests.conftest import RE # noqa
from bluesky.plans import count
from bluesky.plan_stubs import trigger_and_read, configure
import event_model
from ophyd.tests.conftest import hw # noqa
import pytest
from .. import UnknownEventType
import warnings

# This line is used to ignore the deprecation warning for bulk_events in tests
warnings.filterwarnings("ignore", message="The document type 'bulk_events'*")


_md = {'reason': 'test', 'user': 'temp user', 'beamline': 'test_beamline'}


# Some useful plans for use in testing


def simple_plan(dets):
    '''A simple plane which runs count with num=5'''
    md = {**_md, **{'test_plan_name': 'simple_plan'}}
    yield from count(dets, num=5, md=md)


def multi_stream_one_descriptor_plan(dets):
    '''A plan that has two streams but on descriptor per stream)'''
    md = {**_md, **{'test_plan_name': 'multi_stream_one_descriptor_plan'}}

    @bluesky.preprocessors.baseline_decorator(dets)
    def _plan(dets):
        yield from count(dets, md=md)

    yield from _plan(dets)


def one_stream_multi_descriptors_plan(dets):
    '''A plan that has one stream but two descriptors per stream)'''
    md = {**_md, **{'test_plan_name': 'simple_plan'}}

    @bluesky.preprocessors.run_decorator(md=md)
    def _internal_plan(dets):
        yield from trigger_and_read(dets)
        for det in dets:
            yield from configure(det, {})
        yield from trigger_and_read(dets)

    yield from _internal_plan(dets)


@pytest.fixture(params=['det', 'direct_img', 'direct_img_list',
                        'det direct_img direct_img_list'],
                scope='function')
def detector_list(hw, request):  # noqa

    def _det_list_func(ignore):
        if request.param in ignore:
            pytest.skip()
        dets = [getattr(hw, det_name) for det_name in request.param.split(' ')]
        return dets

    return _det_list_func


@pytest.fixture(params=['event', 'bulk_events', 'event_page'],
                scope='function')
def event_type(request):

    def _event_type_func(ignore):
        if request.param in ignore:
            pytest.skip()
        return request.param

    return _event_type_func


@pytest.fixture(params=[simple_plan, multi_stream_one_descriptor_plan,
                        one_stream_multi_descriptors_plan],
                scope='function')
def plan_type(request):
    def _plan_type_func(ignore):
        if request.param in ignore:
            pytest.skip()
        return request.param

    return _plan_type_func


@pytest.fixture()
def generate_data(RE, detector_list, event_type):  # noqa
    '''A fixture that returns event data for a number of test cases.

    Returns a list of (name, doc) tuples for the plan passed in as an arg.

    Parameters
    ----------
    RE : object
        pytest fixture object imported from `bluesky.test.conftest`
    detector_list : list
        pytest fixture defined in `suitcase.utils.conftest` which returns a
        list of detectors
    event_type : list
        pytest fixture defined in `suitcase.utils.conftest` which returns a
        list of 'event_types'.
    '''

    def _generate_data_func(plan, ignore=None):
        '''Generates data to be used for testing of suitcase.*.export(..)
        functions

        Parameters
        ----------
        plan : the plan to use to generate the test data

        Returns
        -------
        collector : list
            A list of (name, doc) tuple pairs generated by the run engine.
        ignore : list, optional
            list of the pytest.fixture parameter 'values' to ignore.
        '''
        if ignore is None:
            ignore = []

        # define the output lists and an internal list.
        collector = []
        event_list = []

        # define the collector function depending on the event_type
        if event_type(ignore) == 'event':
            def collect(name, doc):
                collector.append((name, doc))
                if name == 'event':
                    event_list.append(doc)
        elif event_type(ignore) == 'event_page':
            def collect(name, doc):
                if name == 'event':
                    event_list.append(doc)
                elif name == 'stop':
                    collector.append(('event_page',
                                      event_model.pack_event_page(
                                          *event_list)))
                    collector.append((name, doc))
                else:
                    collector.append((name, doc))
        elif event_type(ignore) == 'bulk_events':
            def collect(name, doc):
                if name == 'event':
                    event_list.append(doc)
                elif name == 'stop':
                    collector.append(('bulk_events', {'primary': event_list}))
                    collector.append((name, doc))
                else:
                    collector.append((name, doc))
        else:
            raise UnknownEventType('Unknown event_type kwarg passed to '
                                   'suitcase.utils.events_data')

        # collect the documents
        RE.subscribe(collect)
        RE(plan(detector_list(ignore)))

        return collector

    return _generate_data_func


@pytest.fixture
def example_data(generate_data, plan_type):
    '''A fixture that returns event data for a number of test cases.

    Returns a function that returns a list of (name, doc) tuples for each of
    the plans in plan_type.

    .. note::

        It is recommended that you use this fixture for testing of
        ``suitcase-*`` export functions, for an example see
        ``suitcase-tiff.tests``. This will mean that future additions to the
        test suite here will be automatically applied to all ``suitcase-*``
        repos. Some important implementation notes:

        1. These fixtures are imported into other suitcase libraries via those
        libraries' ``conftest.py`` file. This is automatically set up by
        suitcases-cookiecutter, and no additional action is required.

        2. If any of the parameters from the fixtures above are not valid for
        the suitcase you are designing and cause testing issues please skip
        them internally by adding them to the ``ignore`` kwarg list via the
        line ``collector = example_data(ignore=[param_to_ignore, ...])``.

    Parameters
    ----------
    generate_data : list
        pytest fixture defined in `suitcase.utils.conftest` which returns a
        function that accepts a plan as an argument and returns name, do pairs
    plan_type : list
        pytest fixture defined in `suitcase.utils.conftest` which returns a
        list of 'plans' to test against.
    '''

    def _example_data_func(ignore=[]):
        '''returns a list of (name, doc) tuples for a number of test cases

        ignore : list optional
            list of the pytest.fixture parameter 'values' to ignore, this is
            also passed down to `generate_data`
        '''

        return generate_data(plan_type(ignore), ignore=ignore)

    return _example_data_func


@pytest.fixture(params=['test-', 'scan_{uid}-'],
                scope='function')
def file_prefix_list(request):  # noqa
    '''Returns a function that provides file_prefixes for testing.
    '''

    def _file_prefix_list_func(ignore=[]):
        if request.param in ignore:
            pytest.skip()
        return request.param

    return _file_prefix_list_func
