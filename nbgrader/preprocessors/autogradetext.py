import re

from traitlets import Dict, Unicode, Bool, observe
from textwrap import dedent

from .. import utils
from . import NbGraderPreprocessor


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

    def _autograde_solution_region(self, cell, language):
        """Find a region in the cell that is delimeted by
        `self.begin_solution_delimeter` and `self.end_solution_delimeter` (e.g.
        ### BEGIN SOLUTION and ### END SOLUTION). Replace that region either
        with the code stub or text stub, depending the cell type.

        This modifies the cell in place, and then returns True if a
        solution region was replaced, and False otherwise.

        """
        # pull out the cell input/source
        lines = cell.source.split("\n")
        self.log.info("Autograding text '%s' ", cell.source)
        new_lines = []
        in_solution = False
        replaced_solution = False

        # replace the cell source
        cell.source = "\n".join(new_lines)

        return replaced_solution

    def preprocess(self, nb, resources):
        language = nb.metadata.get("kernelspec", {}).get("language", "python")
        #if language not in self.code_stub:
        #    raise ValueError(
        #        "language '{}' has not been specified in "
        #        "AutogradeTextSolutions.code_stub".format(language))

        resources["language"] = language
        nb, resources = super(AutogradeTextSolutions, self).preprocess(nb, resources)
        if 'celltoolbar' in nb.metadata:
            del nb.metadata['celltoolbar']
        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        # replace solution regions with the relevant stubs
        language = resources["language"]

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
            replaced_solution = self._autograde_solution_region(cell, language)
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
