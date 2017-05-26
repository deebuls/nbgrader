import re

from traitlets import Dict, Unicode, Bool, observe
from textwrap import dedent

from .. import utils
from ..api import Gradebook, MissingEntry
from . import NbGraderPreprocessor

from ..plugins.nlp import find_synonyms
from ..plugins.nlp import tokenize_sentence
from ..plugins.nlp import filter_stop_words
from ..plugins.nlp import filter_repeated_words
from ..plugins.nlp import edit


class AutogradeTextSolutions(NbGraderPreprocessor):

    enforce_metadata = Bool(
        True,
        help=dedent(
            """
            Whether or not to complain if cells containing solutions regions are
            not marked as solution cells. WARNING: this will potentially cause
            things to break if you are using the full nbgrader pipeline. ONLY
            disable this option if you are only ever planning to use nbgrader
            assign.
            """
        )
    ).tag(config=True)

    def _load_config(self, cfg, **kwargs):
        super(AutogradeTextSolutions, self)._load_config(cfg, **kwargs)

    def _autograde_solution_region(self, cell, solution):
        """Find a region in the cell that is delimeted by
        This modifies the cell in place, and then returns True if a
        solution region was replaced, and False otherwise.

        """
        # pull out the cell input/source
        lines = cell.source.split("\n")
        self.log.info("Autograding text '%s' ", cell.source)
        self.log.info("with solution text '%s' ", solution)
        new_lines = []
        in_solution = False
        replaced_solution = False

        sentence_1 = solution
        tokenized_sentence_1 = tokenize_sentence(sentence_1)
        tokenized_sentence_1 = filter_stop_words(tokenized_sentence_1)
        tokenized_sentence_1 = filter_repeated_words(tokenized_sentence_1)
        sentence_2 = cell.source
        tokenized_sentence_2 = tokenize_sentence(sentence_2)
        tokenized_sentence_2 = filter_stop_words(tokenized_sentence_2)
        tokenized_sentence_2 = filter_repeated_words(tokenized_sentence_2)
        connections = find_synonyms(tokenized_sentence_1, tokenized_sentence_2)
        edited_sentence = edit(tokenize_sentence(sentence_2), connections)
        self.log.info("Matched words: %s", edited_sentence)
        cell.source = edited_sentence
        # replace the cell source
        #cell.source = "\n".join(new_lines)

        return replaced_solution

    def preprocess(self, nb, resources):
        # pull information from the resources
        self.notebook_id = resources['nbgrader']['notebook']
        self.assignment_id = resources['nbgrader']['assignment']
        self.db_url = resources['nbgrader']['db_url']

        # connect to the database
        self.gradebook = Gradebook(self.db_url)

        with self.gradebook:
            nb, resources = super(AutogradeTextSolutions, self).preprocess(nb, resources)

        if 'celltoolbar' in nb.metadata:
            del nb.metadata['celltoolbar']
        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        #find grade_id of cell, if not available then return
        grade_id = cell.metadata.get('nbgrader', {}).get('grade_id', None)
        if grade_id is None:
            return cell, resources

        try:
            source_cell = self.gradebook.find_source_cell(
                grade_id,
                self.notebook_id,
                self.assignment_id)
        except MissingEntry:
            self.log.warning("Cell '{}' does not exist in the database".format(grade_id))
            del cell.metadata.nbgrader['grade_id']
            return cell, resources

        # determine whether the cell is a solution/grade cell
        is_solution = utils.is_solution(cell)

        # determine wheter the cell is a grade cell
        is_grade = utils.is_grade(cell)

        # determine whether the cell is a markdown cell
        is_markdown = (cell.cell_type == 'markdown')

        # if it manually graded markdown cell
        # -- if its a solution and grade and its markdown
        # Then run autograde on this text
        if is_solution and is_grade and is_markdown :
            replaced_solution = self._autograde_solution_region(cell, source_cell.source)
        else:
            replaced_solution = False

        # check that it is marked as a solution cell if we replaced a solution
        # region -- if it's not, then this is a problem, because the cell needs
        # to be given an id
        if not is_solution and replaced_solution:
            if self.enforce_metadata:
                raise RuntimeError(
                    "Solution region detected in a non-solution cell; please make sure "
                    "all solution regions are within solution cells."
                )

        return cell, resources
