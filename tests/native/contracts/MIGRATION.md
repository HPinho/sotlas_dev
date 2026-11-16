# Native test migration

All assertions and data below now live in checked-in `.sotlas` programs.
The old Python-generated cases are replaced, not skipped. Pass cases return
zero on success and a nonzero check number on failure. Reject cases require
native check/build failure and preserved output. Fault cases require the
platform integer-divide-by-zero process result.

| Previous test | Sotlas case | Mode |
| --- | --- | --- |
| `NativeJsonTests.test_bad_unicode_and_control_bytes_fail_closed` | `json_unicode_bad` | pass |
| `NativeJsonTests.test_empty_string_and_empty_collections_have_distinct_missing_results` | `json_empty` | pass |
| `NativeJsonTests.test_forged_string_span_cannot_include_leading_whitespace` | `json_forged_string` | pass |
| `NativeJsonTests.test_invalid_descriptors_and_wrong_value_types` | `json_metadata` | pass |
| `NativeJsonTests.test_nested_objects_arrays_and_scalar_kinds` | `json_nested` | pass |
| `NativeJsonTests.test_nesting_limit_and_wide_arrays` | `json_depth` | pass |
| `NativeJsonTests.test_raw_number_preserves_precision_and_u32_is_strict` | `json_numbers` | pass |
| `NativeJsonTests.test_raw_utf8_keys_escaped_keys_and_first_duplicate` | `json_keys` | pass |
| `NativeJsonTests.test_string_capacity_and_overlap_fail_before_writes` | `json_copy_fail` | pass |
| `NativeJsonTests.test_syntax_rejections_and_original_byte_offsets` | `json_invalid` | pass |
| `NativeJsonTests.test_top_level_values_numbers_and_json_whitespace` | `json_values` | pass |
| `NativeJsonTests.test_unicode_escapes_decoding_and_embedded_nul` | `json_unicode` | pass |
| `NativeJsonWriterTests.test_capacity_failure_includes_comma_and_preserves_bytes_and_state` | `json_writer_capacity` | pass |
| `NativeJsonWriterTests.test_corrupt_control_and_backing_alias_are_rejected_without_writes` | `json_writer_corrupt` | pass |
| `NativeJsonWriterTests.test_depth_limit_is_recoverable_and_reader_accepts_boundary` | `json_writer_depth` | pass |
| `NativeJsonWriterTests.test_empty_storage_reset_and_invalid_control` | `json_writer_empty` | pass |
| `NativeJsonWriterTests.test_escape_capacity_and_bad_keys_preserve_object_state` | `json_writer_escape_capacity` | pass |
| `NativeJsonWriterTests.test_exact_capacity_empty_keys_strings_and_numbers` | `json_writer_exact` | pass |
| `NativeJsonWriterTests.test_invalid_utf8_number_and_source_alias_do_not_write` | `json_writer_invalid` | pass |
| `NativeJsonWriterTests.test_nested_objects_arrays_and_readback` | `json_writer_nested` | pass |
| `NativeJsonWriterTests.test_state_errors_do_not_publish_or_consume_pending_values` | `json_writer_state` | pass |
| `NativeJsonWriterTests.test_string_escaping_preserves_unicode_controls_and_nul` | `json_writer_escapes` | pass |
| `NativeJsonWriterTests.test_unicode_keys_duplicate_names_and_state_reset` | `json_writer_keys` | pass |
| `NativeJsonExchangeTests.test_array_iteration_covers_every_value_kind_and_nested_values` | `json_iter_array` | pass |
| `NativeJsonExchangeTests.test_combined_depth_is_checked_before_copy` | `json_copy_depth` | pass |
| `NativeJsonExchangeTests.test_copy_alias_and_invalid_value_fail_without_mutation` | `json_copy_alias` | pass |
| `NativeJsonExchangeTests.test_copy_all_kinds_and_keep_lexical_numbers_and_whitespace` | `json_copy_values` | pass |
| `NativeJsonExchangeTests.test_copy_capacity_failure_does_not_append_separator_or_consume_slot` | `json_copy_capacity` | pass |
| `NativeJsonExchangeTests.test_cursor_rejects_interior_positions_wrong_kinds_and_false_done` | `json_iter_invalid` | pass |
| `NativeJsonExchangeTests.test_empty_container_iteration_and_depth_ignores_escaped_delimiters` | `json_depth_and_empty` | pass |
| `NativeJsonExchangeTests.test_object_iteration_preserves_duplicates_order_and_decoded_keys` | `json_iter_object` | pass |
| `NativeNarrowDivisionTests.test_all_u8_operands_match_wide_reference_and_division_identity` | `narrow_div_u8_exhaustive` | pass |
| `NativeNarrowDivisionTests.test_dynamic_zero_divisors_trap_for_both_widths_and_operations` | `narrow_div_zero_u8q` | fault |
| `NativeNarrowDivisionTests.test_dynamic_zero_divisors_trap_for_both_widths_and_operations` | `narrow_div_zero_u8r` | fault |
| `NativeNarrowDivisionTests.test_dynamic_zero_divisors_trap_for_both_widths_and_operations` | `narrow_div_zero_u16q` | fault |
| `NativeNarrowDivisionTests.test_dynamic_zero_divisors_trap_for_both_widths_and_operations` | `narrow_div_zero_u16r` | fault |
| `NativeNarrowDivisionTests.test_fields_indexed_places_and_single_evaluation` | `narrow_div_places` | pass |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_0` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_1` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_2` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_3` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_4` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_5` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_6` | reject |
| `NativeNarrowDivisionTests.test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected` | `narrow_div_invalid_7` | reject |
| `NativeNarrowDivisionTests.test_module_constants_keep_the_declared_byte_and_word_types` | `narrow_div_constants` | pass |
| `NativeNarrowDivisionTests.test_module_constants_keep_the_declared_byte_and_word_types` | `narrow_div_bad_const_0` | reject |
| `NativeNarrowDivisionTests.test_module_constants_keep_the_declared_byte_and_word_types` | `narrow_div_bad_const_1` | reject |
| `NativeNarrowDivisionTests.test_nested_arithmetic_casts_calls_and_conditional_values` | `narrow_div_expressions` | pass |
| `NativeNarrowDivisionTests.test_u16_boundary_pairs_preserve_unsigned_width` | `narrow_div_u16_boundaries` | pass |
