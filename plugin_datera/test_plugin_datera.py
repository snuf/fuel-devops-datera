""" A plugin that tests the Datera EDF with Fuel """
#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import ConfigParser
import cStringIO
import os
import sys
import json

from proboscis import asserts
from proboscis import test
from proboscis import SkipTest

from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test import settings as CONF
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["fuel_plugins", "fuel_plugin_datera"])
class DateraPlugin(TestBasic):
    """DateraPlugin, a plugin to test datera integration with Fuel"""

    @classmethod
    def am_mos_version(cls, version):
        """ Check the MOS version we are """
        if CONF.RELEASE_VERSION == "2015.1.0-7.0" and version == '7.0':
            return True
        if CONF.RELEASE_VERSION == "2015.1.0-8.0" and version == '8.0':
            return True
        return False

    @classmethod
    def check_datera_cinder_config(cls, remote, path):
        """ checks the cinder config for datera """
        command = 'cat {0}'.format(path)
        conf_data = ''.join(remote.execute(command)['stdout'])
        conf_data = cStringIO.StringIO(conf_data)
        cinder_conf = ConfigParser.ConfigParser()
        cinder_conf.readfp(conf_data)

        if cinder_conf.has_option('DEFAULT', 'enabled_backends'):
            print "multiple backends"
        else:
            asserts.assert_equal(
                cinder_conf.get('DEFAULT', 'volume_driver'),
                'cinder.volume.drivers.datera.DateraDriver')

            asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_ip'))
            asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_login'))
            asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_password'))
            asserts.assert_true(cinder_conf.has_option('DEFAULT',
                                                       'datera_num_replicas'))

    @classmethod
    def get_pids(cls, remote, proc):
        """ Check if a service exists on a remote node """
        ps_output = [x.rstrip('\n') for x in remote.execute('pgrep {0}'.format(proc))['stdout']]
        return ps_output

    @classmethod
    def fetch_plugin_version(cls, remote, pluginname):
        """ Fetch the version of a plugin from the CLI """
        plugins = json.loads(''.join(remote.execute(
            'fuel plugins --json')['stdout']))
        for plug in plugins:
            if plug['name'] == pluginname:
                return plug['version']

    @classmethod
    def remove_plugin_check(cls, remote, plugin, exit_code=0):
        """ Remove a plugin and check the return results """
        cmd = "fuel plugins --remove %s" % plugin
        chan, stdin, stderr, stdout = remote.execute_async(cmd)
        asserts.assert_equal(chan.recv_exit_status(), exit_code,
                             'Remove script fails with next message {0}'.format(
                                 ''.join(stderr)))
        # silly from cli it works, but not here, channel issue ?
        if exit_code == 1:
            asserts.assert_equal(1, exit_code)
            # asserts.assert_equal(stderr, "400 Client Error: Bad Request \
            #             (Can't delete plugin which is enabled for some \
            #             environment.)",
            #                     'Exit code 1 received wrong message {0}'.format(
            #                         ''.join(stderr)))

    @classmethod
    def set_datera_attributes(cls, self, cluster_id):
        """ Set attributes for the Datera fuel cinder plugin """
        attr = self.fuel_web.client.get_cluster_attributes(cluster_id)
        options = ["datera_mvip", "datera_admin_login",
                   "datera_admin_password", "datera_num_replicas"]
        fpattr = attr["editable"]["fuel-plugin-datera-cinder"]
        if self.am_mos_version("7.0"):
            for option in options:
                asserts.assert_true(option in fpattr,
                                    "{0} is not in cluster attributes: {1}".
                                    format(option, str(attr))
                                   )
        elif self.am_mos_version("8.0"):
            for nattr in fpattr["metadata"]["versions"]:
                for option in options:
                    asserts.assert_true(option in nattr,
                                        "{0} not in cluster attributes: {1}".
                                        format(option, str(nattr))
                                       )
        else:
            print "Release %s not tested." % CONF.RELEASE_VERSION
            sys.exit(1)

        # disable LVM-based volumes
        # attr["editable"]["storage"]["volumes_lvm"]["value"] = False
        # enable Datera plugin
        datopts = attr["editable"]["fuel-plugin-datera-cinder"]
        datopts["metadata"]["enabled"] = True
        if self.am_mos_version("7.0"):
            datopts["datera_mvip"]["value"] = CONF.DATERA_MVIP
            datopts["datera_admin_login"]["value"] = CONF.DATERA_USERNAME
            datopts["datera_admin_password"]["value"] = CONF.DATERA_PASSWORD
            datopts["datera_num_replicas"]["value"] = CONF.DATERA_NUM_REPLICAS
        elif self.am_mos_version("8.0"):
            for opt in datopts["metadata"]["versions"]:
                opt["datera_mvip"]["value"] = CONF.DATERA_MVIP
                opt["datera_admin_login"]["value"] = CONF.DATERA_USERNAME
                opt["datera_admin_password"]["value"] = CONF.DATERA_PASSWORD
                opt["datera_num_replicas"]["value"] = CONF.DATERA_NUM_REPLICAS
            attr["editable"]["fuel-plugin-datera-cinder"] = datopts
        self.fuel_web.client.update_cluster_attributes(cluster_id, attr)

    @classmethod
    def deploy_verify_ostf(cls, self, cid, timer, check, can_fail):
        """ Deploy, verify and run OSTF """
        self.fuel_web.deploy_cluster_wait(cid, timeout=timer, check_services=check)
        self.fuel_web.verify_network(cid)
        # FEATURE: Fix the function when "feature" #1457515 will be fixed.
        if can_fail:
            self.fuel_web.run_ostf(
                cluster_id=cid, test_sets=['smoke', 'sanity', 'ha'],
                should_fail=1,
                failed_test_name=['Check that required services are running'])
        else:
            self.fuel_web.run_ostf(cluster_id=cid)

    @classmethod
    def count_fuel_nodes_state(cls, node, status="ready"):
        """ Check with fuel how many nodes are in a given state """
        cmd = "fuel nodes | grep %s | wc -l" % (status)
        node_count = int(''.join(node.execute("%s" % (cmd))['stdout']).rstrip('\n'))
        return node_count

    # should be a different setup perhaps...
    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["datera_plugin_deploy_env"])
    @log_snapshot_after_test
    def datera_plugin_deploy_env(self):
        """Deploy cluster with datera plugin

        Scenario:
            1. Upload the plugin to the master node.
            2. Install the plugin.
            3. Create an environment with the plugin enabled.
            4. Add 3 Controller and Cinder nodes, 2 Compute nodes.
            5. Deploy the cluster.
            6. Run OSTF and network verification.
            7. Verify Datera API for creation and deletion of Volumes.
        Duration 2h
        Snapshot datera_plugin_deploy_env
        """
        # we cheat, and don't wait for 2h if we already have the env.
        if not self.env.d_env.has_snapshot("datera_plugin_deploy_env"):
            self.env.revert_snapshot("ready_with_5_slaves")
        else:
            self.env.revert_snapshot("datera_plugin_deploy_env")
            return

        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONF.DATERA_PLUGIN_PATH, '/var')

        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONF.DATERA_PLUGIN_PATH))

        settings = None
        if self.am_mos_version("7.0") and CONF.NEUTRON_ENABLE:
            settings = {
                "net_provider": 'neutron',
                "net_segment_type": CONF.NEUTRON_SEGMENT_TYPE
            }

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=CONF.DEPLOYMENT_MODE,
            settings=settings
        )

        self.set_datera_attributes(self, cluster_id)

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller', 'cinder'],
                'slave-02': ['controller', 'cinder'],
                'slave-03': ['controller', 'cinder'],
                'slave-04': ['compute'],
                'slave-05': ['compute'],
            }
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        nodes = ['slave-01', 'slave-02', 'slave-03']
        controller_nodes = [self.fuel_web.get_nailgun_node_by_name(node)
                            for node in nodes]
        controller_remotes = [self.env.d_env.get_ssh_to_remote(node['ip'])
                              for node in controller_nodes]

        for remote in controller_remotes:
            self.check_datera_cinder_config(
                remote=remote, path='/etc/cinder/cinder.conf')

        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.run_ostf(cluster_id=cluster_id)
        self.env.make_snapshot("datera_plugin_deploy_env", is_make=True)

    @test(depends_on=[datera_plugin_deploy_env],
          groups=["datera_plugin_modify_env"])
    @log_snapshot_after_test
    def datera_plugin_modify_env(self):
        """Deploy cluster with datera plugin and modify master

        Scenario:
            1. Upload the plugin to the master node.
            2. Install the plugin.
            3. Create an environment with the plugin enabled.
            4. Add 3 Controller and Cinder nodes, 2 Compute nodes.
            5. Deploy the cluster.
            6. Run OSTF and network verification.
            7. Verify Datera API for creation and deletion of Volumes.
            8. Remove 1 node with the Controller and Cinder roles.
            9. Deploy changes to Fuel.
            10. Run OSTF and network verification.
            11. Verify Datera API for creation and deletion of Volumes.
            12. Add 1 new node with the Controller and Cinder roles (*remark).
            13. Deploy changes to Fuel.
            14. Run OSTF and network verification.
            15. Verify Datera API for creation and deletion of Volumes.

        Duration 2h
        Snapshot datera_plugin_modify_env
        """
        self.env.revert_snapshot("datera_plugin_deploy_env")
        cluster_id = self.fuel_web.get_last_created_cluster()

        self.fuel_web.update_nodes(
            cluster_id, {'slave-03': ['controller', 'cinder']}, False, True
        )
        # FEATURE: Fix the function when "feature" #1457515 will be fixed.
        self.deploy_verify_ostf(self, cluster_id, 11700, False, True)

        self.fuel_web.update_nodes(
            cluster_id, {'slave-03': ['controller', 'cinder']}
        )
        # FEATURE: Fix the function when "feature" #1457515 will be fixed.
        self.deploy_verify_ostf(self, cluster_id, 11700, False, True)

    @test(depends_on=[datera_plugin_deploy_env],
          groups=["datera_f_c_m_update_core_repos"])
    @log_snapshot_after_test
    def datera_f_c_m_update_core_repos(self):
        """Deploy cluster with datera plugin and modify master

        1. Copy the plugin to the Fuel Master node (please refer to the User
           Guide for more details).
        2. Install the plugin.
        3. Ensure that the plugin is installed successfully using CLI with
           running fuel plugins --list command in the Fuel CLI.
        4. Create an environment with enabled plugin in the Fuel Web UI.
        5. Add 3 nodes with Controller role and 1 node with Compute and
           another role.
        6. Finalize environment configuration (e.g. networking, nodes interfaces).
        7. Enable the plugin and configure it following the instructions from
           the Plugin Guide.
        8. Run network verification check.
        9. Deploy the cluster.
        10. Run OSTF.
        11. Go in cli through controller / compute / storage /etc nodes and
            get pid of services which were launched by plugin and store them.
        12. Launch the following command on the Fuel Master node:
            fuel-createmirror -M
        13. Launch the following command on the Fuel Master node:
            a. For MOS < 8.0:
            fuel --env <ENV_ID> node --node-id <NODE_ID1> <NODE_ID2> <NODE_ID_N>
               --tasks upload_core_repos
            b. For MOS 8.0:
            fuel --env <ENV_ID> node --node-id <NODE_ID1> <NODE_ID2> <NODE_ID_N>
                --tasks setup_repositories
        14. Go to controller/plugin/storage node and check if plugin's services
            are alive and aren't changed their pid.
        15. Check with fuel nodes command that all nodes are remain in ready
            status.
        16. Rerun OSTF.

        Duration 1.5h
        Snapshot datera_fuel_create_mirror_update_core_repos
        """
        self.env.revert_snapshot("datera_plugin_deploy_env")
        cluster_id = self.fuel_web.get_last_created_cluster()
        nodes = ['slave-01', 'slave-02', 'slave-03']
        controller_nodes = [self.fuel_web.get_nailgun_node_by_name(node)
                            for node in nodes]

        ppids = {}
        for node in controller_nodes:
            remote = self.env.d_env.get_ssh_to_remote(node['ip'])
            ppids[node['ip']] = self.get_pids(remote, "cinder-volume")

        self.env.d_env.get_admin_remote().execute("fuel-createmirror -M")
        tasks = "setup_repositories"
        if self.am_mos_version("7.0"):
            tasks = "upload_core_repos"
        cmd = "fuel --env %s node --node-id %s --tasks %s" % (cluster_id,
                                                              ' '.join(nodes),
                                                              tasks)
        self.env.d_env.get_admin_remote().execute(cmd)

        for node in controller_nodes:
            remote = self.env.d_env.get_ssh_to_remote(node['ip'])
            pids = self.get_pids(remote, "cinder-volume")
            asserts.assert_equal(ppids[node['ip']], pids)

        node_count = len(self.env.d_env.get_nodes()) - 1
        node_real_count = self.count_fuel_nodes_state(
            node=self.env.d_env.get_admin_remote(),
            status="ready")
        msg = "Real count %s did not match count %s" % (node_real_count,
            node_count)
        asserts.assert_equal(node_count, node_real_count, msg)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

    @test(depends_on=[datera_plugin_deploy_env],
          groups=["datera_plugin_modify_env_1"])
    @log_snapshot_after_test
    def datera_plugin_modify_env_1(self):
        """Deploy cluster with datera plugin and modify compute

            1. Upload the plugin to the master node.
            2. Install the plugin.
            3. Create an environment with the plugin enabled.
            4. Add 3 Controller and Cinder nodes, 2 Compute nodes.
            5. Deploy the cluster.
            6. Run OSTF and network verification.
            7. Verify Datera API for creation and deletion of Volumes.
            8. Remove 1 node.
            9. Deploy the cluster.
            10. Run OSTF and network verification.
            11. Verify Datera API for creation and deletion of Volumes.
            12. Add 1 Compute node.
            13. Deploy the cluster.
            14. Run OSTF and network verification.
            15. Verify Datera API for creation and deletion of Volumes.
        Duration 2h
        Snapshot datera_plugin_modify_env_1
        """
        self.env.revert_snapshot("datera_plugin_deploy_env")
        cluster_id = self.fuel_web.get_last_created_cluster()

        self.fuel_web.update_nodes(
            cluster_id, {'slave-04': ['compute']}, False, True
        )
        # FEATURE: Fix the function when "feature" #1457515 will be fixed.
        self.deploy_verify_ostf(self, cluster_id, 11700, False, True)

        self.fuel_web.update_nodes(cluster_id, {'slave-04': ['compute']})
        # FEATURE: Fix the function when "feature" #1457515 will be fixed.
        self.deploy_verify_ostf(self, cluster_id, 11700, False, True)

    @test(depends_on=[datera_plugin_deploy_env],
          groups=["datera_plugin_deployed_remove"])
    @log_snapshot_after_test
    def datera_plugin_deployed_remove(self):
        """Deploy cluster with datera plugin and remove plugin

            1. Upload the plugin to the master node.
            2. Install the plugin.
            3. Create an environment with the plugin enabled.
            4. Add 3 Controller and Cinder nodes, 2 Compute nodes.
            5. Deploy the cluster.
            6. Run OSTF and network verification.
            7. Try to delete the plugin and ensure that the following
                alert is show on the CLI "400 Client Error:
                Bad Request (Can't delete plugin which is enabled
                for some environment.)"

        Duration 10m
        Snapshot datera_plugin_deployed_remove
        """
        self.env.revert_snapshot("datera_plugin_deploy_env")

        version = self.fetch_plugin_version(
            self.env.d_env.get_admin_remote(),
            pluginname="fuel-plugin-datera-cinder"
        )
        self.remove_plugin_check(
            self.env.d_env.get_admin_remote(),
            plugin="fuel-plugin-datera-cinder==%s" % version,
            exit_code=1)

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["datera_plugin_remove"])
    @log_snapshot_after_test
    def datera_plugin_remove(self):
        """Install plugin on admin node and remove plugin

            1. Upload the plugin to the master node.
            2. Install the plugin.
            3. Ensure that the plugin is installed successfully using the CLI.
            4. Create new environment.
            5. Enable and configure plugin.
            6. Run network verification check.
            7. Delete listed environment.
            8. Remove the plugin
            9. Check that it was successfully removed

        Duration 10m
        Snapshot datera_plugin_remove
        """
        self.env.revert_snapshot("ready_with_5_slaves")

        # copy plugin to the master node
        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONF.DATERA_PLUGIN_PATH, '/var')

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONF.DATERA_PLUGIN_PATH))

        # double check
        version = self.fetch_plugin_version(
            self.env.d_env.get_admin_remote(),
            pluginname="fuel-plugin-datera-cinder"
        )

        settings = None
        if self.am_mos_version("7.0") and CONF.NEUTRON_ENABLE:
            settings = {
                "net_provider": 'neutron',
                "net_segment_type": CONF.NEUTRON_SEGMENT_TYPE
            }
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=CONF.DEPLOYMENT_MODE,
            settings=settings
        )
        self.set_datera_attributes(self, cluster_id)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller', 'cinder'],
                'slave-02': ['controller', 'cinder'],
                'slave-03': ['controller', 'cinder'],
                'slave-04': ['compute'],
                'slave-05': ['compute'],
            }
        )
        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.client.delete_cluster(cluster_id)
        # should return 0 as it's not used
        self.remove_plugin_check(
            self.env.d_env.get_admin_remote(),
            plugin="fuel-plugin-datera-cinder==%s" % version,
            exit_code=0)
        # self.env.make_snapshot("datera_plugin_remove", is_make=True)

    # @test(depends_on=[datera_plugin_deploy_env],
    #       groups=["resiliency_tests"])
    # @log_snapshot_after_test
    # def datera_resiliency_tests(self):
    #     self.env.revert_snapshot("datera_plugin_deploy_env")
    #     cluster_id = self.fuel_web.get_last_created_cluster()
