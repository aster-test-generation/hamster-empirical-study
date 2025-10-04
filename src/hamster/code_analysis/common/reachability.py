from collections import deque
import re
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Set, Tuple, Dict, Counter, Union
from cldk.analysis.java import JavaAnalysis
from hamster.code_analysis.utils import constants


@dataclass
class ReachabilityConfig:
    allow_repetition: bool = False  # On same level
    only_helpers: bool = False
    add_extended_class: bool = False


class Reachability:
    def __init__(self, analysis: JavaAnalysis):
        self.analysis = analysis
        self._reachability_cache: Dict[Tuple, Dict[str, List[str]]] = {}

    def get_helper_methods(
        self,
        qualified_class_name: str,
        method_signature: str,
        depth: int = constants.CONTEXT_SEARCH_DEPTH,
        add_extended_class: bool = False,
        allow_repetition: bool = False,
    ) -> Dict[str, List[str]]:
        """
        Retrieves the helper methods reachable from the given method within the specified depth.

        Args:
            qualified_class_name: The qualified name of the class.
            method_signature: The method signature.
            depth: The depth for search in call hierarchy.
            add_extended_class: If set to True, include methods from classes extended by the given class.
            allow_repetition: If set to True, allow visiting the same method multiple times in the same depth level.

        Returns:
            Dict[str, List[str]]: A map from class names to method signatures of helper methods.
        """
        method_details = self.analysis.get_method(
            qualified_class_name, method_signature
        )
        visited: Set[Tuple[str, str]] = set()
        reachability_config = ReachabilityConfig(
            allow_repetition=allow_repetition,
            add_extended_class=add_extended_class,
            only_helpers=True,
        )
        reachability_key = self._get_reachability_key(
            qualified_class_name, method_signature, reachability_config
        )

        if reachability_key in self._reachability_cache:
            reachable_methods_by_class = self._reachability_cache[reachability_key]
        else:
            reachable_methods_by_class: Dict[str, List[str]] = (
                self._collect_reachable_methods(
                    qualified_class_name,
                    method_signature,
                    depth,
                    reachability_config,
                    visited,
                )
            )
            self._reachability_cache[reachability_key] = reachable_methods_by_class

        final_reachable_methods: Dict[str, List[str]] = {}
        for class_name in reachable_methods_by_class:
            for method_signature in reachable_methods_by_class[class_name]:
                method = self.analysis.get_method(
                    qualified_class_name, method_signature
                )
                if (
                    method
                    and (class_name != qualified_class_name or method != method_details)
                    and method.code.isascii()
                ):
                    final_reachable_methods.setdefault(class_name, []).append(
                        method_signature
                    )
        return final_reachable_methods

    def _collect_reachable_methods(
        self,
        qualified_class_name: str,
        method_signature: str,
        depth: int,
        reachability_config: ReachabilityConfig,
        visited: Set[Tuple[str, str]] = None,
    ) -> Dict[str, List[str]]:
        """
        Collects reachable methods starting from the given method within a given depth.

        Args:
            qualified_class_name: The qualified name of the class.
            method_signature: The method signature.
            depth: The depth for search in call hierarchy.
            reachability_config: The configurations for reachability computation.
            visited: The set of tuples that have already been visited.

        Returns:
            Dict[str, List[str]]: A map from class names to method signatures of reachable methods.
        """
        if depth < 0:
            return {}

        if visited is None:
            visited: Set[Tuple[str, str]] = set()

        # Normalize constructors
        simple_class_name = qualified_class_name.split(".")[-1]
        if method_signature.startswith(f"{simple_class_name}("):
            method_signature = method_signature.replace(
                f"{simple_class_name}(", "<init>("
            )

        basic_key = (qualified_class_name, method_signature)

        # Check for an existing depth-level duplicate
        if basic_key in visited:
            return {}
        visited.add(basic_key)

        reachability_key = self._get_reachability_key(
            qualified_class_name, method_signature, reachability_config
        )

        # Check if already expanded in cache
        if reachability_key in self._reachability_cache:
            return self._reachability_cache[reachability_key]

        method_details = self.analysis.get_method(
            qualified_class_name, method_signature
        )

        # Check for ensuring valid method
        if not method_details:
            return {}

        # Seed result dictionary with the current method to start
        reachable_methods: Dict[str, List[str]] = {
            qualified_class_name: [method_signature]
        }

        # Determine extended classes if needed
        extend_list = []
        if reachability_config.add_extended_class:
            class_details = self.analysis.get_class(qualified_class_name)
            extend_list = class_details.extends_list if class_details else []

        child_counter: Counter[Tuple[str, str]] = Counter()

        # Handle interface-based call sites
        interface_map: Dict[str, List[str]] = {}
        for site in method_details.call_sites:
            receiver = site.receiver_type
            receiver_class = self.analysis.get_class(receiver)
            if receiver_class and receiver_class.is_interface:
                processed_sig = site.callee_signature
                interface_map.setdefault(receiver, []).append(processed_sig)

        # For all call sites with interface receiver types, collect the method signature
        for interface, callee_sigs in interface_map.items():
            for concrete_class in self.get_concrete_classes(interface_class=interface):
                # All concrete classes that implement interface
                if (
                    not reachability_config.only_helpers
                    or concrete_class == qualified_class_name
                ) or concrete_class in extend_list:
                    for callee_sig in callee_sigs:
                        child_counter[(concrete_class, callee_sig)] += 1

        # Handle direct symbol-table callees
        callees = self.analysis.get_callees(
            source_class_name=qualified_class_name,
            source_method_declaration=method_signature,
            using_symbol_table=True,
        ).get("callee_details", [])
        for callee_details in callees:
            callee_class = callee_details["callee_method"].klass
            if (
                not reachability_config.only_helpers
                or callee_class == qualified_class_name
            ) or callee_class in extend_list:
                callee_sig = callee_details["callee_method"].method.signature
                num_calls = max(len(callee_details.get("calling_lines", [])), 1)
                # Note: CLDK sometimes returns empty lists for calling_lines; assume if it exists, it occurs at least once
                # CLDK currently has a strange bug with calling_lines returning empty lists...
                # if num_calls == 0:
                #     raise Exception("A called method has no calling lines...")
                child_counter[(callee_class, callee_sig)] += num_calls

        # Now process unique children
        for child_key, num_calls in child_counter.items():
            child_class, child_sig = child_key
            child_reachable_methods = self._collect_reachable_methods(
                child_class, child_sig, depth - 1, reachability_config, visited
            )
            if reachability_config.allow_repetition:
                add_times = num_calls
            else:
                add_times = 1
            for _ in range(add_times):
                for child_c_class, methods_list in child_reachable_methods.items():
                    reachable_methods.setdefault(child_c_class, []).extend(methods_list)

        # This will allow a parent to revisit at the same level
        if reachability_config.allow_repetition:
            visited.remove(basic_key)

        return reachable_methods

    def get_concrete_classes(self, interface_class: str) -> List[str]:
        """
        Returns a list of concrete classes that implement the given interface class.

        Args:
            interface_class: The interface class.

        Returns:
            List[str]: List of concrete classes that implement the given interface class.
        """
        all_classes_in_application = self.analysis.get_classes()
        concrete_classes = []
        for qualified_class, class_details in all_classes_in_application.items():
            if (
                not class_details.is_interface
                and "abstract" not in class_details.modifiers
            ):
                if interface_class in class_details.implements_list:
                    concrete_classes.append(qualified_class)
        return concrete_classes

    def _get_reachability_key(
        self,
        qualified_class_name: str,
        method_signature: str,
        reachability_config: ReachabilityConfig,
    ) -> Tuple:
        """
        Generates a unique key for the reachability computation based on the input parameters.

        Args:
            qualified_class_name: The qualified name of the class.
            method_signature: The method signature.
            reachability_config: The configurations for reachability computation.

        Returns:
            Tuple: A unique reachability key.
        """
        reachability_key = (
            qualified_class_name,
            method_signature,
            reachability_config.allow_repetition,
            reachability_config.add_extended_class,
            reachability_config.only_helpers,
        )
        return reachability_key

    def get_visible_class_methods(
        self,
        qualified_class_name: str,
        *,
        visibility_mode: Literal[
            "public", "same_package", "same_package_or_subclass"
        ] = "public",
        include_metadata: bool = False,
    ) -> Dict[str, List[Union[str, Dict[str, Any]]]]:
        """
        Retrieves methods reachable from qualified class along its inheritance graph. Precedence looks at the class itself,
        then superclasses, then interfaces (level-order).

        Args:
            qualified_class_name: The qualified name of the class.
            visibility_mode: The visibility mode. Either "public", "same_package", or "same_package_or_subclass".
            include_metadata: Include metadata in the output.

        Returns:
            Dict[str, List[str]] mapping owner (class or interface) -> list of method signatures

        Raises:
            ClassNotFoundError: If the qualified_class_name cannot be found.
        """
        root_details = self.analysis.get_class(qualified_class_name)
        if not root_details:
            raise Exception(
                f"Class {qualified_class_name} not found.",
                extra_info={"qualified_class_name": qualified_class_name},
            )

        def _accept(owner: str, method_sig: str) -> bool:
            return self.is_accessible_from(
                owner,
                method_sig,
                accessor_class=qualified_class_name,
                mode=visibility_mode,
            )

        def _meta(owner: str, method_sig: str) -> Dict[str, Any]:
            method_details = self.analysis.get_method(owner, method_sig)
            owner_pkg = self.package_of(owner)
            mods = list(method_details.modifiers) if method_details else []
            visibility = (
                "private"
                if "private" in mods
                else (
                    "public"
                    if "public" in mods
                    else "protected" if "protected" in mods else "package-private"
                )
            )
            return {
                "method_signature": method_sig,
                "declaring_qualified_class_name": owner,
                "modifiers": mods,
                "visibility": visibility,
            }

        result: Dict[str, List[Union[str, Dict[str, Any]]]] = {}
        seen_sigs: set[str] = set()

        def _add_methods(owner: str) -> None:
            for method_sig in self.analysis.get_methods_in_class(owner):
                if method_sig in seen_sigs:
                    continue
                if _accept(owner, method_sig):
                    seen_sigs.add(method_sig)
                    if include_metadata:
                        result.setdefault(owner, []).append(_meta(owner, method_sig))
                    else:
                        result.setdefault(owner, []).append(method_sig)

        # Methods on the class itself
        _add_methods(qualified_class_name)

        # Superclasses in BFS order
        super_queue: deque[str] = deque(root_details.extends_list or [])
        visited_supers: set[str] = set(root_details.extends_list or [])
        super_bfs_order: List[str] = []

        while super_queue:
            sup_cls = super_queue.popleft()
            super_bfs_order.append(sup_cls)
            _add_methods(sup_cls)

            sup_details = self.analysis.get_class(sup_cls)
            if sup_details and sup_details.extends_list:
                for next_sup in sup_details.extends_list:
                    if next_sup not in visited_supers:
                        visited_supers.add(next_sup)
                        super_queue.append(next_sup)

        # Interfaces in BFS order
        iface_queue: deque[str] = deque()
        visited_ifaces: set[str] = set()

        def _enqueue_interfaces(owner: str) -> None:
            owner_details = self.analysis.get_class(owner)
            if owner_details and owner_details.implements_list:
                for iface in owner_details.implements_list:
                    if iface not in visited_ifaces:
                        visited_ifaces.add(iface)
                        iface_queue.append(iface)

        _enqueue_interfaces(qualified_class_name)
        for sup in super_bfs_order:
            _enqueue_interfaces(sup)

        while iface_queue:
            iface = iface_queue.popleft()
            _add_methods(iface)

            iface_details = self.analysis.get_class(iface)
            if iface_details and iface_details.extends_list:
                for parent_iface in iface_details.extends_list:
                    if parent_iface not in visited_ifaces:
                        visited_ifaces.add(parent_iface)
                        iface_queue.append(parent_iface)

        return result

    def is_accessible_from(
        self,
        owner_class: str,
        method_signature: str,
        *,
        accessor_class: Optional[str] = None,
        mode: Literal["public", "same_package", "same_package_or_subclass"] = "public",
    ) -> bool:
        class_details = self.analysis.get_class(owner_class)
        if not class_details:
            raise Exception(
                f"Class {owner_class} not found.",
            )

        method_details = self.analysis.get_method(owner_class, method_signature)
        if not method_details:
            raise Exception(
                f"Method {method_signature} not found in class {owner_class}.",
            )

        mods = set(method_details.modifiers)
        owner_pkg = self.package_of(owner_class)

        # Public methods and interface/annotation non-private methods are always visible
        if "public" in mods:
            return True
        if class_details.is_interface or class_details.is_annotation_declaration:
            if "private" not in mods:
                return True

        # Implicit public constructor for public class
        if (
            method_details.is_constructor
            and method_details.is_implicit
            and "public" in class_details.modifiers
        ):
            return True

        # Determined all public accessibility options
        if mode == "public":
            return False

        # Determine accessor package
        acc_pkg = self.package_of(accessor_class) if accessor_class else ""

        # Same package rules
        if owner_pkg == acc_pkg:
            if "private" in mods:
                return False
            return True
        # Protected and package-private allowed in same package

        # If different package and not public, it is not accessible
        if mode == "same_package":
            return False

        # Check for subclass inheritance of protected method
        if (
            "protected" in mods
            and accessor_class
            and self.is_subclass_of(accessor_class, owner_class)
        ):
            return True

        return False

    def is_subclass_of(self, sub_class: str, super_class: str) -> bool:
        if not sub_class or not super_class or sub_class == super_class:
            return False

        sub_info = self.analysis.get_class(sub_class)
        if not sub_info:
            return False

        stack = sub_info.extends_list
        seen = set()

        while stack:
            curr = stack.pop()
            if curr in seen:
                continue
            if curr == super_class:
                return True
            seen.add(curr)

            curr_info = self.analysis.get_class(curr)
            if curr_info:
                parents = curr_info.extends_list
                stack.extend(parents)

        return False

    @staticmethod
    def package_of(qualified_class_name: str) -> str:
        i = qualified_class_name.rfind(".")
        return qualified_class_name[:i] if i != -1 else ""
