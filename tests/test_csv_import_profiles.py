"""Tests for the remembered CSV import setups.

Each test writes to a settings key of its own, so running the suite never
disturbs the setups a real user has saved.
"""
from __future__ import annotations

import pytest

from loading.csv import profiles as profiles_module
from loading.csv.profiles import (
    MAX_PROFILES, ImportProfile, clear_profiles, load_profiles, save_profile,
)


@pytest.fixture(scope="session")
def qapp():
    """Return a process-wide offscreen QApplication for the settings store."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(qapp, monkeypatch):
    """Point the profile store at a scratch key and empty it afterwards."""
    monkeypatch.setattr(profiles_module, "SETTINGS_KEY",
                        "csv_import/test_setups")
    clear_profiles()
    yield
    clear_profiles()


def make_profile(label="run.csv", header_row=3, isotope_label="48Ti",
                 column="Ti48 -> 64"):
    """Return a profile with one mapping, for use in the tests.

    Args:
        label (str): Name shown in the chooser.
        header_row (int): Line holding the column names.
        isotope_label (str): Label of the mapped isotope.
        column (str): Column the isotope was mapped from.

    Returns:
        ImportProfile: A populated setup.
    """
    return ImportProfile(
        created="2026-07-30T19:55:00",
        label=label,
        file_count=12,
        header_row=header_row,
        delimiter=",",
        params={'time_column': 'Time [Sec]', 'time_unit': 'seconds',
                'dwell_time_ms': 0.1, 'use_calculated_dwell': True,
                'data_type': 'Counts'},
        mappings=[{'column': column,
                   'isotope': {'symbol': 'Ti', 'mass': 47.94795,
                               'label': isotope_label,
                               'element_name': 'Titanium', 'abundance': 73.7}}],
        removed_columns=["Notes"],
    )


class TestStoringSetups:
    """Saving and reading back."""

    def test_nothing_is_remembered_to_begin_with(self, store):
        """A fresh install offers no setups."""
        assert load_profiles() == []

    def test_a_setup_survives_a_round_trip(self, store):
        """Everything needed to rebuild an import is stored."""
        save_profile(make_profile())
        restored = load_profiles()[0]
        assert restored.header_row == 3
        assert restored.removed_columns == ["Notes"]
        assert restored.params['data_type'] == 'Counts'
        assert restored.mappings[0]['column'] == "Ti48 -> 64"
        assert restored.mappings[0]['isotope']['label'] == "48Ti"

    def test_the_newest_setup_comes_first(self, store):
        """The list is ordered most recent first."""
        save_profile(make_profile(label="older"))
        save_profile(make_profile(label="newer", header_row=5))
        assert [p.label for p in load_profiles()] == ["newer", "older"]

    def test_only_the_last_few_are_kept(self, store):
        """The list is capped so it stays choosable."""
        for index in range(MAX_PROFILES + 3):
            save_profile(make_profile(label=f"run{index}", header_row=index))
        assert len(load_profiles()) == MAX_PROFILES

    def test_repeating_a_setup_does_not_stack_it_up(self, store):
        """Importing the same batch twice leaves one entry, not two."""
        save_profile(make_profile())
        save_profile(make_profile())
        assert len(load_profiles()) == 1

    def test_a_changed_setup_is_kept_separately(self, store):
        """A different header row is a different setup."""
        save_profile(make_profile(header_row=3))
        save_profile(make_profile(header_row=7))
        assert len(load_profiles()) == 2

    def test_forgetting_empties_the_list(self, store):
        """Clearing removes every setup."""
        save_profile(make_profile())
        clear_profiles()
        assert load_profiles() == []

    def test_a_corrupt_store_is_treated_as_empty(self, store, monkeypatch):
        """Unreadable preferences never stop an import."""
        profiles_module._settings().setValue(
            profiles_module.SETTINGS_KEY, "{not json")
        assert load_profiles() == []


class TestDescriptions:
    """What the chooser shows for each setup."""

    def test_lists_the_isotopes(self, store):
        """The summary names what the setup maps."""
        assert "48Ti" in make_profile().describe()

    def test_says_when_nothing_is_mapped(self, store):
        """A setup with no mappings says so rather than showing an empty list."""
        empty = ImportProfile(file_count=4)
        assert "nothing mapped" in empty.describe()

    def test_long_isotope_lists_are_shortened(self, store):
        """A wide setup does not produce an unreadable line."""
        profile = make_profile()
        profile.mappings = [
            {'column': f"c{i}", 'isotope': {'label': f"{i}X"}}
            for i in range(12)
        ]
        summary = profile.describe()
        assert "and 6 more" in summary

    def test_the_save_time_is_readable(self, store):
        """The stored timestamp renders as a date and time."""
        assert "2026" in make_profile().when()

    def test_an_unparseable_time_is_left_out(self, store):
        """A bad timestamp does not raise, it simply shows nothing."""
        profile = make_profile()
        profile.created = "not a date"
        assert profile.when() == ""


class TestSetupPickerDialog:
    """Building and driving the chooser itself.

    These construct the real dialog. The store was covered before this class
    existed but the widget was not, and a signal firing during construction
    crashed it the first time it was opened for real.
    """

    def test_it_builds_with_setups(self, store, qapp):
        """Opening the picker with saved setups does not raise."""
        from loading.csv.dialog import RecentSetupsDialog
        picker = RecentSetupsDialog([make_profile(label="a"),
                                     make_profile(label="b", header_row=9)])
        assert picker.list.count() == 2
        picker.deleteLater()

    def test_it_builds_with_none(self, store, qapp):
        """Opening the picker with nothing saved does not raise."""
        from loading.csv.dialog import RecentSetupsDialog
        picker = RecentSetupsDialog([])
        assert picker.list.count() == 0
        assert picker.use_button.isEnabled() is False
        picker.deleteLater()

    def test_the_first_setup_starts_selected(self, store, qapp):
        """The newest setup is ready to confirm straight away."""
        from loading.csv.dialog import RecentSetupsDialog
        picker = RecentSetupsDialog([make_profile(label="newest"),
                                     make_profile(label="older", header_row=9)])
        assert picker.selected_profile().label == "newest"
        assert picker.use_button.isEnabled() is True
        picker.deleteLater()

    def test_choosing_another_row_changes_the_result(self, store, qapp):
        """Selecting the second entry returns the second setup."""
        from loading.csv.dialog import RecentSetupsDialog
        picker = RecentSetupsDialog([make_profile(label="newest"),
                                     make_profile(label="older", header_row=9)])
        picker.list.setCurrentRow(1)
        assert picker.selected_profile().label == "older"
        picker.deleteLater()

    def test_each_row_shows_what_the_setup_does(self, store, qapp):
        """The row text names the files, the isotopes and the save time."""
        from loading.csv.dialog import RecentSetupsDialog
        picker = RecentSetupsDialog([make_profile(label="run.csv")])
        text = picker.list.item(0).text()
        assert "run.csv" in text and "48Ti" in text and "2026" in text
        picker.deleteLater()

    def test_forgetting_empties_the_picker(self, store, qapp):
        """Forget all clears the store and closes the chooser."""
        from loading.csv.dialog import RecentSetupsDialog
        save_profile(make_profile())
        picker = RecentSetupsDialog(load_profiles())
        picker._forget_all()
        assert load_profiles() == []
        assert picker.cleared() is True
        picker.deleteLater()


class TestApplyTargetsDialog:
    """The file chooser shown by Apply to files."""

    def test_it_builds_and_ticks_everything(self, store, qapp):
        """Every candidate file starts selected."""
        from loading.csv.dialog import ApplyTargetsDialog
        picker = ApplyTargetsDialog([(1, "b.csv"), (2, "c.csv")], "a.csv")
        assert picker.selected_indexes() == [1, 2]
        assert picker.apply_button.isEnabled() is True
        picker.deleteLater()

    def test_unticking_everything_disables_apply(self, store, qapp):
        """Applying to nothing is not offered."""
        from loading.csv.dialog import ApplyTargetsDialog
        picker = ApplyTargetsDialog([(1, "b.csv")], "a.csv")
        picker._set_all(False)
        assert picker.selected_indexes() == []
        assert picker.apply_button.isEnabled() is False
        picker.deleteLater()
