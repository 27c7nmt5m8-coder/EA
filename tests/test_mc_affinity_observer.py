"""Identity, privacy and contamination contracts for read-only observation."""
import importlib.util
import json
import unittest


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.mc_affinity_observer'),
                             'read-only observer is not implemented')
        from tools import mc_affinity_observer as observer
        self.m = observer

    def row(self, pid=10, born=100, parent=1, affinity=255, name='terminal64.exe'):
        return dict(pid=pid, born=born, parent=parent, affinity=affinity,
                    name=name, image='C:/test/' + name, owner='SAME_USER',
                    cpu_100ns=0, threads=3, priority=32, groups=[0], cpu_sets=[])

    def test_stable_mask_is_observed_without_expected_mask(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row()], 0)
        o.sample([self.row()], 1)
        self.assertEqual(o.summary()['affinity_status'], 'AFFINITY_STABLE')
        self.assertEqual(o.summary()['changes'], [])

    def test_middle_placement_unknown_does_not_disappear_on_recovery(self):
        o=self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()],0)
        unknown=self.row();unknown['cpu_sets']='UNKNOWN'
        o.sample([unknown],1)
        o.sample([self.row()],2)
        self.assertFalse(o.summary()['comparison_eligible'])
        self.assertIn((10,100),o.summary()['unknown_identities'])

    def test_change_has_interval_and_does_not_invent_caller(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row(affinity=1)], 2)
        o.sample([self.row()], 3)
        change = o.summary()['changes'][0]
        self.assertEqual((change['before'], change['after']), (1, 255))
        self.assertEqual((change['after_sample_s'], change['observed_s']), (2, 3))
        self.assertEqual(change['attribution'], 'UNATTRIBUTED')
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_pid_reuse_is_not_continuous_identity(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row()], 0)
        o.sample([self.row(born=200)], 1)
        self.assertEqual(len(o.summary()['changes']), 0)
        self.assertFalse(o.summary()['comparison_eligible'])
        self.assertEqual(o.events[0]['kind'], 'PROCESS_ABSENT')

    def test_unowned_tester_is_contamination(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row(), self.row(pid=11, parent=99, name='metatester64.exe')], 0)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_tester_child_enrolment_needs_live_parent_identity(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row(), self.row(pid=11, born=101, parent=10, name='metatester64.exe')], 0)
        self.assertEqual(o.roles[(11, 101)], 'owned_descendant')
        o.sample([self.row(pid=12, born=102, parent=10, name='metatester64.exe')], 1)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_updater_is_contamination_even_if_owned_child(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        row = self.row(pid=11, born=101, parent=10)
        row['image'] = 'C:/test/liveupdate/terminal64.exe'
        o.sample([self.row(), row], 0)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_unknown_affinity_cannot_pass(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        o.sample([self.row(affinity='UNKNOWN')], 0)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_cpu_usage_is_delta_not_absolute_total(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        first, second = self.row(), self.row()
        first['cpu_100ns'], second['cpu_100ns'] = 10000000, 15000000
        o.sample([first], 0)
        o.sample([second], 1)
        self.assertEqual(o.last[(10, 100)]['cpu_one_core_pct'], 50)

    def test_credentials_and_accounts_never_survive_command_redaction(self):
        raw = 'terminal64.exe /login:12345678 /password:"mock secret" /config:C:/test/run.ini token=mock-token-value'
        redacted = self.m.redact_command(raw, ['mock secret'])
        for value in ('12345678', 'mock secret', 'mock-token-value'):
            self.assertNotIn(value, redacted)
        self.assertNotIn('/config:C:/test/run.ini', redacted)

    def test_approved_tester_destinations_remain_identifiable(self):
        self.assertIn('/config:CodexMCMultiProbe_N2_M0_NORMAL.ini', self.m.redact_command(
            'terminal64.exe /config:C:/test/CodexMCMultiProbe_N2_M0_NORMAL.ini'))

    def test_required_identity_never_seen_prevents_comparison(self):
        o = self.m.Observer({(10,100):'owned_terminal',(20,200):'controller'})
        o.sample([self.row()], 0)
        o.sample([self.row()], 1)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_single_sample_and_unconfirmed_disappearance_do_not_pass(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()], 0)
        self.assertFalse(o.summary()['comparison_eligible'])
        o.sample([self.row()], 1)
        o.sample([], 2)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_foreign_nonnative_child_is_contamination(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        child = self.row(pid=11,born=101,parent=10,name='helper.exe')
        child['owner'] = 'OTHER_USER'
        o.sample([self.row(),child],0)
        o.sample([self.row(),child],1)
        self.assertFalse(o.summary()['comparison_eligible'])
        self.assertTrue(o.summary()['contamination'])

    def test_placement_change_is_excluded(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()],0)
        row = self.row()
        row['cpu_sets'] = [2]
        o.sample([row],1)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_unknown_sample_does_not_fabricate_affinity_changes(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()],0)
        o.sample([self.row(affinity='UNKNOWN')],1)
        o.sample([self.row()],2)
        self.assertEqual(o.summary()['changes'],[])
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_unknown_py_argument_and_profile_are_never_preserved(self):
        for raw in ('python.exe script.py --password secret.py', 'terminal64.exe /profile:SECRET-EXAMPLE'):
            result = self.m.redact_command(raw)
            self.assertNotIn('secret.py',result)
            self.assertNotIn('SECRET-EXAMPLE',result)

    def test_nonfinite_overhead_is_unknown(self):
        self.assertEqual(self.m.overhead_status(1,float('inf')),'UNKNOWN')

    def test_required_registration_does_not_allow_missing_terminal(self):
        o = self.m.Observer({(10,100):'controller'})
        o.register((20,200),'owned_terminal')
        o.sample([self.row()],0)
        o.sample([self.row()],1)
        self.assertFalse(o.summary(completed=True)['comparison_eligible'])

    def test_unknown_image_is_not_proven_process_identity(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        row = self.row()
        row['image'] = 'UNKNOWN'
        o.sample([row],0)
        o.sample([row],1)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_reappearing_required_process_marks_observation_gap(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()],0)
        o.sample([self.row()],1)
        o.sample([],2)
        o.sample([self.row()],3)
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_scoped_snapshot_follows_grandchildren_without_ancestor_siblings(self):
        api = self.m.WindowsReadOnly.__new__(self.m.WindowsReadOnly)
        rows = {1:self.row(pid=1,parent=0,name='parent.exe'),
                10:self.row(parent=1,name='controller.exe'),
                11:self.row(pid=11,parent=10,name='helper.exe'),
                12:self.row(pid=12,parent=11,name='grandchild.exe'),
                13:self.row(pid=13,parent=1,name='unrelated.exe')}
        api.entries = lambda:rows
        api.read = lambda row:row
        self.assertEqual({r['pid'] for r in api.snapshot({10})},{1,10,11,12})

    def test_short_owned_editor_does_not_fabricate_full_interval_stability(self):
        o = self.m.Observer({(10,100):'owned_terminal'})
        o.sample([self.row()],0)
        editor = self.row(pid=11,born=101,parent=10,name='MetaEditor64.exe')
        o.sample([self.row(),editor],1)
        o.sample([self.row()],2)
        result = o.summary()
        self.assertTrue(result['comparison_eligible'])
        self.assertEqual(result['auxiliary_interval_coverage'],'UNKNOWN_FOR_SHORT_LIVED_PROCESSES')

    def test_unknown_command_arguments_are_redacted_by_default(self):
        result = self.m.redact_command('python.exe script.py --mystery SECRET-EXAMPLE')
        self.assertNotIn('SECRET-EXAMPLE', result)

    def test_empty_observation_is_unknown(self):
        o = self.m.Observer({(10, 100): 'owned_terminal'})
        self.assertEqual(o.summary()['affinity_status'], 'UNKNOWN')
        self.assertFalse(o.summary()['comparison_eligible'])

    def test_overhead_budget_is_fail_closed(self):
        self.assertEqual(self.m.overhead_status(0.1, 10), 'ACCEPTABLE')
        self.assertEqual(self.m.overhead_status(1, 10), 'OBSERVER_OVERHEAD_TOO_HIGH')
        self.assertEqual(self.m.overhead_status(0, 0), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
