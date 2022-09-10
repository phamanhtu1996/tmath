from abc import ABCMeta, abstractmethod, abstractproperty

import six

class BaseExamFormat(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def __init__(self, exam):
        self.exam = exam

    @abstractproperty
    def name(self):
        """
        Name of this exam format. Should be invoked with gettext_lazy.

        :return: str
        """
        raise NotImplementedError
    
    @abstractmethod
    def update_participation(self, participation):
        """
        Updates a ExamParticipation object's score, cumtime, and format_data fields based on this exam format.
        Implementations should call ExamParticipation.save().

        :param participation: A ExamParticipation object.
        :return: None
        """
        raise NotImplementedError()
    
    @abstractmethod
    def display_user_problem(self, participation, exam_problem):
        """
        Returns the HTML fragment to show a user's performance on an individual problem. This is expected to use
        information from the format_data field instead of computing it from scratch.

        :param participation: The ExamParticipation object linking the user to the exam.
        :param exam_problem: The ExamProblem object representing the problem in question.
        :return: An HTML fragment, marked as safe for Jinja2.
        """
        raise NotImplementedError()

    @abstractmethod
    def display_participation_result(self, participation):
        """
        Returns the HTML fragment to show a user's performance on the whole exam. This is expected to use
        information from the format_data field instead of computing it from scratch.

        :param participation: The ExamParticipation object.
        :return: An HTML fragment, marked as safe for Jinja2.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_problem_breakdown(self, participation, exam_problems):
        """
        Returns a machine-readable breakdown for the user's performance on every problem.

        :param participation: The ExamParticipation object.
        :param exam_problems: The list of ExamProblem objects to display performance for.
        :return: A list of dictionaries, whose content is to be determined by the exam system.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_label_for_problem(self, index):
        """
        Returns the problem label for a given zero-indexed index.

        :param index: The zero-indexed problem index.
        :return: A string, the problem label.
        """
        raise NotImplementedError()

    @classmethod
    def best_solution_state(cls, points, total):
        if not points:
            return 'failed-score'
        if points == total:
            return 'full-score'
        return 'partial-score'

